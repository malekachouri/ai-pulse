import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select, text

from app.ingestion.catalog import DEFAULT_SOURCES
from app.ingestion.runner import lock_key
from app.ingestion.scheduling import due_sources, next_due, recover_stale_jobs, source_health
from app.models import Article, CollectionJob, Source
from app.models.enums import JobStatus
from tests.conftest import SEEDED
from tests.ingestion_helpers import NOW, MockHttp, ingest, js, make_source, xml

FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Good item</title><link>https://example.test/a</link><guid>a</guid><pubDate>Sun, 08 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>No link</title><guid>b</guid><pubDate>Sun, 08 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>From the future</title><link>https://example.test/c</link><guid>c</guid><pubDate>Mon, 30 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Bad scheme</title><link>javascript:alert(1)</link><guid>d</guid></item>
</channel></rss>"""


def test_migration_seeded_catalog():
    assert SEEDED["sources"] == len(DEFAULT_SOURCES) >= 25


async def test_validation_rejects_bad_records_and_marks_partial(session_factory):
    url = "https://example.test/feed"
    sid = await make_source(session_factory, "rss", url, config={"categories": ["devops"]})
    job = await ingest(session_factory, sid, MockHttp({url: xml(FEED)}))
    assert job.status == JobStatus.PARTIAL
    assert job.items_created == 1 and job.items_skipped == 3  # 3 invalid
    reasons = " ".join(e["error"] for e in job.errors)
    assert "invalid original URL" in reasons and "future" in reasons
    assert {e["stage"] for e in job.errors} == {"validate"}


async def test_records_without_category_are_rejected(session_factory):
    url = "https://example.test/feed"
    sid = await make_source(session_factory, "rss", url)  # no default categories; titles match no rule
    job = await ingest(session_factory, sid, MockHttp({url: xml(FEED)}))
    assert job.items_created == 0 and any("no category" in e["error"] for e in job.errors)


async def test_fetch_failure_is_atomic_and_tracked(session_factory):
    url = "https://example.test/feed"
    sid = await make_source(
        session_factory, "rss", url, config={"categories": ["devops"]}, checkpoint={"etag": '"old"'}
    )
    job = await ingest(session_factory, sid, MockHttp({url: httpx.Response(500)}))
    assert job.status == JobStatus.FAILED and "HTTP 500" in job.error
    assert job.errors[0]["stage"] == "fetch" and job.errors[0]["status"] == 500
    async with session_factory() as s:
        src = await s.get(Source, sid)
        assert src.consecutive_failures == 1 and src.last_error and src.checkpoint == {"etag": '"old"'}
        assert await s.scalar(select(func.count(Article.id))) == 0
    ok = await ingest(session_factory, sid, MockHttp({url: xml(FEED)}))
    async with session_factory() as s:
        assert (await s.get(Source, sid)).consecutive_failures == 0 and ok.status == JobStatus.PARTIAL


async def test_malformed_payload_fails_job_cleanly(session_factory):
    url = "https://status.example.test/api"
    sid = await make_source(session_factory, "statuspage", url, config={"provider": "Xco"})
    bad = {"page": {"url": "https://status.example.test"}, "incidents": [{"id": "1"}, {"id": "2", "name": "ok",
           "status": "resolved", "created_at": "2026-11-08T10:00:00Z"}]}  # fmt: skip
    job = await ingest(session_factory, sid, MockHttp({url: js(bad)}))
    assert job.status == JobStatus.PARTIAL and job.items_created == 1
    assert job.errors[0]["stage"] == "normalize" and "KeyError" in job.errors[0]["error"]


async def test_concurrent_runs_are_prevented(session_factory):
    url = "https://example.test/feed"
    sid = await make_source(session_factory, "rss", url, config={"categories": ["devops"]})
    async with session_factory() as holder:
        await holder.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_key(sid)})
        assert await ingest(session_factory, sid, MockHttp({url: xml(FEED)})) is None
        await holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key(sid)})
    assert await ingest(session_factory, sid, MockHttp({url: xml(FEED)})) is not None


async def test_disabled_sources_skip_scheduled_but_allow_manual(session_factory):
    url = "https://example.test/feed"
    sid = await make_source(session_factory, "rss", url, config={"categories": ["devops"]}, enabled=False)
    assert await ingest(session_factory, sid, MockHttp({url: xml(FEED)}), trigger="schedule") is None
    assert (
        await ingest(session_factory, sid, MockHttp({url: xml(FEED)}), trigger="manual")
    ).trigger == "manual"


async def test_scheduling_backoff_and_stale_recovery(session_factory):
    a = await make_source(session_factory, "rss", "https://a.test/f", slug="a", poll_interval_minutes=60)
    b = await make_source(session_factory, "rss", "https://b.test/f", slug="b", poll_interval_minutes=60)
    c = await make_source(
        session_factory, "rss", "https://c.test/f", slug="c", poll_interval_minutes=60, consecutive_failures=2
    )
    await make_source(session_factory, "rss", "https://d.test/f", slug="d", enabled=False)
    async with session_factory() as s:
        s.add_all([
            CollectionJob(source_id=a, status=JobStatus.SUCCEEDED, started_at=NOW - timedelta(minutes=30)),
            CollectionJob(source_id=b, status=JobStatus.SUCCEEDED, started_at=NOW - timedelta(minutes=90)),
            CollectionJob(source_id=c, status=JobStatus.FAILED, started_at=NOW - timedelta(minutes=90)),
            CollectionJob(source_id=a, status=JobStatus.RUNNING, started_at=NOW - timedelta(hours=3)),
        ])  # fmt: skip
        await s.commit()
        due = {x.slug for x in await due_sources(s, NOW)}
    assert due == {"b"}  # a ran 30 min ago; c backs off to 4h after 2 failures; d disabled
    async with session_factory() as s:
        src_c = await s.get(Source, c)
        assert next_due(src_c, NOW) == NOW + timedelta(hours=4)
        assert await recover_stale_jobs(s, NOW) == 1
        await s.commit()
        stale = await s.scalar(select(CollectionJob).where(CollectionJob.error.like("Worker lost%")))
        assert stale.status == JobStatus.FAILED


@pytest.mark.parametrize(
    ("enabled", "failures", "last_ok_minutes", "expected"),
    [(False, 0, 10, "disabled"), (True, 3, 10, "failing"), (True, 1, 10, "degraded"), (True, 0, 10, "healthy"),
     (True, 0, 600, "stale"), (True, 0, None, "never_run")],
)  # fmt: skip
def test_source_health(enabled, failures, last_ok_minutes, expected):
    src = Source(enabled=enabled, consecutive_failures=failures, poll_interval_minutes=60,
                 last_success_at=None if last_ok_minutes is None else NOW - timedelta(minutes=last_ok_minutes))  # fmt: skip
    assert source_health(src, None, NOW).status == expected


async def test_unknown_connector_fails_job(session_factory):
    sid = await make_source(session_factory, "does_not_exist", "https://x.test")
    job = await ingest(session_factory, sid, MockHttp({}))
    assert job.status == JobStatus.FAILED and "Unknown connector" in job.error


async def test_lock_key_is_signed_64bit():
    for _ in range(100):
        k = lock_key(uuid.uuid4())
        assert -(2**63) <= k < 2**63
