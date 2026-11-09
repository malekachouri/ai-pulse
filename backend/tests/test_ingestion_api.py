from datetime import UTC, datetime, timedelta

from app.ingestion.queue import QueueUnavailableError
from app.models import CollectionJob
from app.models.enums import JobStatus
from tests.conftest import PASSWORD, make_admin, register_and_login
from tests.ingestion_helpers import make_source


class FakeQueue:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[str, str]] = []
        self.fail = fail

    def enqueue_ingest(self, source_id: str, trigger: str) -> str:
        if self.fail:
            raise QueueUnavailableError("The ingestion queue (Redis) is unavailable; try again shortly")
        self.sent.append((source_id, trigger))
        return f"task-{len(self.sent)}"


async def _staff(client, session_factory):
    await register_and_login(client, "ops@example.com")
    await make_admin(session_factory, "ops@example.com")
    r = await client.post("/api/v1/auth/login", json={"email": "ops@example.com", "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_connectors_listing_has_config_schemas(client, session_factory):
    h = await _staff(client, session_factory)
    items = {c["key"]: c for c in (await client.get("/api/v1/admin/connectors", headers=h)).json()}
    assert {"rss", "nvd", "cisa_kev", "github_trending", "statuspage", "aws_status_rss"} <= set(items)
    assert "page_size" in items["nvd"]["config_schema"]["properties"]


async def test_source_config_is_validated(client, session_factory):
    h = await _staff(client, session_factory)
    base = {"slug": "x-status", "name": "X status", "source_type": "status_page", "url": "https://status.x.test/api",
            "default_item_type": "incident"}  # fmt: skip
    r = await client.post("/api/v1/admin/sources", json={**base, "connector": "nope"}, headers=h)
    assert r.status_code == 400 and "Unknown connector" in r.json()["error"]["message"]
    r = await client.post(
        "/api/v1/admin/sources", json={**base, "connector": "statuspage", "config": {}}, headers=h
    )
    assert r.status_code == 400 and r.json()["error"]["details"][0]["loc"] == ["provider"]
    r = await client.post("/api/v1/admin/sources", json={**base, "connector": "statuspage",
                                                         "config": {"provider": "Xco", "typo_option": 1}}, headers=h)  # fmt: skip
    assert r.status_code == 400
    r = await client.post(
        "/api/v1/admin/sources",
        json={**base, "connector": "statuspage", "config": {"provider": "Xco"}},
        headers=h,
    )
    assert r.status_code == 201
    sid = r.json()["id"]
    r = await client.patch(f"/api/v1/admin/sources/{sid}", json={"config": {"provider": ""}}, headers=h)
    assert r.status_code == 400
    r = await client.patch(
        f"/api/v1/admin/sources/{sid}", json={"reset_checkpoint": True, "enabled": False}, headers=h
    )
    assert r.status_code == 200 and r.json()["checkpoint"] == {} and r.json()["enabled"] is False


async def test_run_now_and_retry(client, session_factory):
    q = FakeQueue()
    client._transport.app.state.task_queue = q  # type: ignore[attr-defined]
    h = await _staff(client, session_factory)
    sid = await make_source(session_factory, "rss", "https://a.test/f", slug="a")
    r = await client.post(f"/api/v1/admin/sources/{sid}/run", headers=h)
    assert r.status_code == 202 and r.json()["task_id"] == "task-1" and q.sent == [(str(sid), "manual")]
    async with session_factory() as s:
        ok = CollectionJob(source_id=sid, status=JobStatus.SUCCEEDED, started_at=datetime.now(UTC))
        bad = CollectionJob(
            source_id=sid, status=JobStatus.FAILED, started_at=datetime.now(UTC), error="HTTP 503"
        )
        s.add_all([ok, bad])
        await s.commit()
        ok_id, bad_id = ok.id, bad.id
    assert (await client.post(f"/api/v1/admin/jobs/{ok_id}/retry", headers=h)).status_code == 409
    r = await client.post(f"/api/v1/admin/jobs/{bad_id}/retry", headers=h)
    assert r.status_code == 202 and q.sent[-1] == (str(sid), "retry")
    logs = (await client.get("/api/v1/admin/audit-logs", params={"action": "job.retry"}, headers=h)).json()
    assert logs["total"] == 1


async def test_queue_unavailable_returns_503(client, session_factory):
    client._transport.app.state.task_queue = FakeQueue(fail=True)  # type: ignore[attr-defined]
    h = await _staff(client, session_factory)
    sid = await make_source(session_factory, "rss", "https://a.test/f", slug="a")
    r = await client.post(f"/api/v1/admin/sources/{sid}/run", headers=h)
    assert r.status_code == 503 and r.json()["error"]["code"] == "queue_unavailable"


async def test_ingestion_status_overview(client, session_factory):
    h = await _staff(client, session_factory)
    now = datetime.now(UTC)
    ok = await make_source(session_factory, "rss", "https://a.test/f", slug="ok", last_success_at=now)
    broken = await make_source(session_factory, "rss", "https://b.test/f", slug="broken", consecutive_failures=4,
                               last_error="HTTP 503 from b.test")  # fmt: skip
    await make_source(session_factory, "rss", "https://c.test/f", slug="off", enabled=False)
    async with session_factory() as s:
        s.add_all([
            CollectionJob(source_id=ok, status=JobStatus.SUCCEEDED, started_at=now - timedelta(minutes=5), finished_at=now),
            CollectionJob(source_id=broken, status=JobStatus.FAILED, started_at=now - timedelta(minutes=2), error="HTTP 503"),
        ])  # fmt: skip
        await s.commit()
    d = (await client.get("/api/v1/admin/ingestion/status", headers=h)).json()
    rows = {x["slug"]: x for x in d["sources"]}
    assert rows["ok"]["health"] == "healthy" and rows["ok"]["last_job"]["duration_seconds"] == 300.0
    assert rows["broken"]["health"] == "failing" and rows["broken"]["last_error"].startswith("HTTP 503")
    assert rows["off"]["health"] == "disabled" and rows["off"]["next_run_at"] is None
    assert d["by_health"] == {"healthy": 1, "failing": 1, "disabled": 1}
    assert d["totals"]["sources"] == 3 and len(d["recent_failures"]) == 1
