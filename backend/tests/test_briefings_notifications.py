"""Phase 7: scheduled personalised briefings, notification preferences and delivery."""

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.ai.briefing import (
    BriefingGenerator,
    DueBriefing,
    due_briefings,
    is_due,
    run_scheduled_briefing,
)
from app.alerts.engine import AlertEngine
from app.models import (
    AIModel,
    AIModelRelease,
    Article,
    DailyBriefing,
    Incident,
    Notification,
    SecurityVulnerability,
    Source,
    User,
    UserPreference,
)
from app.models.enums import (
    BriefingFrequency,
    IncidentStatus,
    ItemType,
    NotificationKind,
    Severity,
    SourceType,
    VerificationStatus,
)
from tests.ai_fakes import providers
from tests.conftest import register_and_login

NOW = datetime.now(UTC).replace(microsecond=0)
MONDAY_1205 = datetime(2026, 11, 9, 12, 5, tzinfo=UTC)  # a Monday


# ------------------------------------------------------------------ helpers
async def _user(s, email: str, **pref) -> User:
    u = User(email=email, password_hash="x", role_id=3)
    s.add(u)
    await s.flush()
    s.add(UserPreference(user_id=u.id, **pref))
    await s.flush()
    return u


def _pref(**kw) -> UserPreference:
    base = dict(
        timezone="UTC", briefing_hour=7, briefing_frequency=BriefingFrequency.DAILY, briefing_weekday=0
    )
    base.update(kw)
    return UserPreference(**base)


@pytest.fixture
async def intel(session_factory):
    """A small synthetic corpus covering every briefing section."""
    async with session_factory() as s:
        src = Source(
            slug="t",
            name="T",
            source_type=SourceType.API,
            connector="rss",
            url="https://t.test",
            default_item_type=ItemType.NEWS,
            is_official=True,
            reliability=0.9,
        )
        s.add(src)
        await s.flush()

        def art(ext: str, title: str, item_type: ItemType, **kw) -> Article:
            a = Article(
                source_id=src.id,
                external_id=ext,
                item_type=item_type,
                title=title,
                url=f"https://t.test/{ext}",
                collected_at=NOW - timedelta(hours=1),
                published_at=NOW - timedelta(hours=2),
                content_hash=ext.ljust(64, "0"),
                verification_status=VerificationStatus.OFFICIAL,
                importance_score=kw.pop("importance_score", 60),
                **kw,
            )
            s.add(a)
            return a

        arts = {
            "news": art("n1", "Agents framework adds RAG memory", ItemType.NEWS),
            "model": art("m1", "Mistral AI releases Codestral 3", ItemType.MODEL_RELEASE),
            "tool": art("t1", "New open-source LLMOps tool", ItemType.TOOL),
            "paper": art("p1", "A survey of retrieval augmentation", ItemType.RESEARCH),
            "bug": art(
                "b1",
                "Crash in acme/infer on startup",
                ItemType.BUG,
                severity=Severity.CRITICAL,
                severity_basis="GitHub label: critical",
            ),
            "cve": art(
                "c1",
                "CVE-2099-2000 in kube-proxy",
                ItemType.VULNERABILITY,
                severity=Severity.CRITICAL,
                severity_basis="NVD CVSS v3.1 9.8",
                importance_score=90,
            ),
            "inc": art("i1", "Elevated API errors", ItemType.INCIDENT),
            "devops": art("d1", "Kubernetes 1.40 released", ItemType.DEVOPS),
        }
        await s.flush()
        s.add(
            SecurityVulnerability(
                article_id=arts["cve"].id,
                cve_id="CVE-2099-2000",
                severity=Severity.CRITICAL,
                cvss_score=9.8,
                published_at=NOW - timedelta(hours=2),
            )
        )
        s.add(
            Incident(
                article_id=arts["inc"].id,
                provider="OpenAI",
                external_id="inc-1",
                title="Elevated API errors",
                status=IncidentStatus.INVESTIGATING,
                impact="major",
                started_at=NOW - timedelta(hours=1),
                status_page_url="https://status.openai.test/inc-1",
                last_verified_at=NOW - timedelta(minutes=5),
            )
        )
        m = AIModel(provider="Mistral AI", name="Codestral")
        s.add(m)
        await s.flush()
        s.add_all(
            [
                AIModelRelease(
                    model_id=m.id,
                    article_id=arts["model"].id,
                    version="3",
                    released_at=NOW - timedelta(hours=3),
                    source_url="https://t.test/m1",
                ),
                # backfilled years-old release: must never notify
                AIModelRelease(
                    model_id=m.id,
                    version="1",
                    released_at=NOW - timedelta(days=400),
                    source_url="https://t.test/m0",
                ),
            ]
        )
        await s.commit()
        return {k: a.id for k, a in arts.items()}


# ------------------------------------------------------------------ scheduling
def test_is_due_catch_up_frequency_and_weekday():
    assert is_due(_pref(briefing_hour=12), MONDAY_1205) == date(2026, 11, 9)
    assert is_due(_pref(briefing_hour=7), MONDAY_1205) == date(2026, 11, 9)  # missed 07:00 -> caught up
    assert is_due(_pref(briefing_hour=13), MONDAY_1205) is None  # not yet
    assert is_due(_pref(briefing_frequency=BriefingFrequency.OFF), MONDAY_1205) is None
    saturday = MONDAY_1205 - timedelta(days=2)
    assert is_due(_pref(briefing_frequency=BriefingFrequency.WEEKDAYS), saturday) is None
    assert is_due(_pref(briefing_frequency=BriefingFrequency.DAILY), saturday) == saturday.date()
    weekly = _pref(briefing_frequency=BriefingFrequency.WEEKLY, briefing_weekday=2)  # Wednesday
    assert is_due(weekly, MONDAY_1205) is None
    assert is_due(weekly, MONDAY_1205 + timedelta(days=2)) == date(2026, 11, 11)
    # 18:05 UTC Monday is already Tuesday 03:05 in Tokyo -> the due date is the local date
    late = MONDAY_1205 + timedelta(hours=6)
    assert is_due(_pref(timezone="Asia/Tokyo", briefing_hour=3), late) == date(2026, 11, 10)
    assert is_due(_pref(timezone="Asia/Tokyo"), late) is None  # 03:05 < 07:00
    # an invalid stored timezone falls back to UTC instead of crashing the scheduler
    assert is_due(_pref(timezone="Mars/Base", briefing_hour=12), MONDAY_1205) == date(2026, 11, 9)


async def test_due_briefings_skip_existing_and_inactive(session_factory):
    async with session_factory() as s:
        a = await _user(s, "a@example.com", briefing_hour=8)
        b = await _user(s, "b@example.com", briefing_hour=8)
        c = await _user(s, "c@example.com", briefing_hour=8)
        c.is_active = False
        s.add(DailyBriefing(user_id=b.id, briefing_date=MONDAY_1205.date(), period_start=NOW, period_end=NOW,
                            generated_at=NOW, sections={}, cited_article_ids=[]))  # fmt: skip
        await s.commit()
        due = await due_briefings(s, MONDAY_1205)
    assert DueBriefing(a.id, MONDAY_1205.date()) in due
    assert all(d.user_id not in (b.id, c.id) for d in due)
    assert DueBriefing(None, MONDAY_1205.date()) in due  # global briefing after 06:00 UTC


# ------------------------------------------------------------------ generation & delivery
async def test_scheduled_briefing_has_every_section_and_notifies_once(session_factory, intel):
    async with session_factory() as s:
        u = await _user(
            s, "p@example.com", interests=["rag", "kubernetes"], followed_technologies=["kube-proxy"]
        )
        await s.commit()
        uid = u.id
    async with session_factory() as s:
        b, notified = await run_scheduled_briefing(s, providers(), uid, NOW.date(), NOW)
        await s.commit()
    assert notified and b is not None
    sec = b.sections
    for key in ("top_ai", "model_releases", "new_tools", "research", "bugs", "vulnerabilities", "incidents",
                "changes", "learning"):  # fmt: skip
        assert key in sec, key
    assert b.executive_summary  # deterministic summary without an LLM
    assert sec["model_releases"][0]["title"] == "Mistral AI releases Codestral 3"
    vuln = sec["vulnerabilities"][0]
    assert vuln["cve_id"] == "CVE-2099-2000" and vuln["severity_basis"] == "NVD CVSS v3.1 9.8"
    inc = sec["incidents"][0]
    assert inc["state"] == "current" and inc["provider"] == "OpenAI"
    assert sec["bugs"][0]["severity_basis"]
    assert sec["meta"]["interests"] == ["rag", "kubernetes"]
    assert any(c["kind"] == "followed" and "kube-proxy" in c["title"] for c in sec["changes"])
    assert all(i["url"].startswith("https://") for k in ("top_ai", "research", "incidents") for i in sec[k])

    # A Celery retry / second dispatch is a no-op: same briefing, no second notification.
    async with session_factory() as s:
        b2, notified2 = await run_scheduled_briefing(
            s, providers(), uid, NOW.date(), NOW + timedelta(minutes=3)
        )
        await s.commit()
        assert b2.id == b.id and b2.generated_at == b.generated_at and not notified2
        notes = (await s.scalars(select(Notification).where(Notification.user_id == uid))).all()
    assert len(notes) == 1
    n = notes[0]
    assert n.kind == NotificationKind.BRIEFING and n.link == f"/briefing?date={NOW.date().isoformat()}"
    assert "briefing" in n.title and n.dedup_key == f"briefing:{NOW.date().isoformat()}"


async def test_concurrent_scheduled_runs_create_one_briefing(session_factory, intel):
    async with session_factory() as s:
        uid = (await _user(s, "c@example.com")).id
        await s.commit()

    async def one() -> None:
        async with session_factory() as s:
            await run_scheduled_briefing(s, providers(), uid, NOW.date(), NOW)
            await s.commit()

    await asyncio.gather(one(), one(), one())
    async with session_factory() as s:
        n_b = await s.scalar(
            select(func.count()).select_from(DailyBriefing).where(DailyBriefing.user_id == uid)
        )
        n_n = await s.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == uid)
        )
    assert n_b == 1 and n_n == 1


async def test_briefing_notification_can_be_disabled_and_inactive_users_skipped(session_factory, intel):
    async with session_factory() as s:
        quiet = await _user(s, "q@example.com", alert_settings={"briefing_ready": False})
        gone = await _user(s, "g@example.com")
        gone.is_active = False
        await s.commit()
        b, notified = await run_scheduled_briefing(s, providers(), quiet.id, NOW.date(), NOW)
        assert b is not None and not notified
        b2, _ = await run_scheduled_briefing(s, providers(), gone.id, NOW.date(), NOW)
        assert b2 is None


async def test_weekly_briefing_covers_a_week_and_changes_track_resolution_and_kev(session_factory, intel):
    async with session_factory() as s:
        u = await _user(s, "w@example.com", briefing_frequency=BriefingFrequency.WEEKLY)
        await s.commit()
        first = await BriefingGenerator(s, providers(), NOW).generate(u, NOW.date() - timedelta(days=1))
        await s.commit()
        assert first.period_end - first.period_start == timedelta(days=7)
        assert first.sections["meta"]["frequency"] == "weekly"
        # Since then: the incident was resolved and the CVE entered CISA KEV.
        inc = await s.scalar(select(Incident))
        inc.status, inc.resolved_at = IncidentStatus.RESOLVED, NOW + timedelta(minutes=30)
        vul = await s.scalar(select(SecurityVulnerability))
        vul.known_exploited, vul.kev_date_added = True, NOW.date()
        await s.commit()
        later = NOW + timedelta(hours=1)
        second = await BriefingGenerator(s, providers(), later).generate(u, NOW.date())
        await s.commit()
    kinds = {c["kind"]: c for c in second.sections["changes"]}
    assert "resolved" in kinds and kinds["resolved"]["url"] == "https://status.openai.test/inc-1"
    assert "exploited" in kinds and "CVE-2099-2000" in kinds["exploited"]["title"]
    assert second.period_start == first.period_end  # continues where the previous briefing stopped
    assert second.sections["meta"]["previous_briefing_date"] == first.briefing_date.isoformat()


async def test_generate_endpoint_uses_the_users_local_date(client, session_factory, intel):
    h = {"Authorization": f"Bearer {await register_and_login(client)}"}
    r = await client.put("/api/v1/preferences", headers=h, json={"timezone": "Pacific/Kiritimati"})  # UTC+14
    assert r.status_code == 200
    b = (await client.post("/api/v1/briefings/generate", headers=h)).json()
    from zoneinfo import ZoneInfo

    assert b["briefing_date"] == datetime.now(ZoneInfo("Pacific/Kiritimati")).date().isoformat()
    assert {"incidents", "bugs", "meta"} <= set(b["sections"])


# ------------------------------------------------------------------ alert rules
async def test_model_release_notifications_follow_provider_preferences(session_factory, intel):
    async with session_factory() as s:
        default = await _user(s, "d@example.com")
        follows = await _user(s, "f@example.com", followed_providers=["Mistral"])
        other = await _user(s, "o@example.com", followed_providers=["OpenAI"])
        explicit = await _user(s, "e@example.com", alert_settings={"model_providers": ["mistral ai"]})
        off = await _user(s, "x@example.com", alert_settings={"model_releases": False})
        await s.commit()
        await AlertEngine(s, NOW).run()
        await s.commit()
        again = await AlertEngine(s, NOW + timedelta(minutes=5)).run()
        await s.commit()
        rows = (
            await s.execute(
                select(Notification.user_id, Notification.title, Notification.link).where(
                    Notification.kind == NotificationKind.MODEL_RELEASE
                )
            )
        ).all()
    got = {uid for uid, _, _ in rows}
    assert {default.id, follows.id, explicit.id} == got
    assert other.id not in got and off.id not in got
    assert all(link == "https://t.test/m1" for _, _, link in rows)  # the 400-day-old release never notifies
    assert all(t == "New model release from Mistral AI: Codestral 3" for _, t, _ in rows)
    assert again.created == 0


# ------------------------------------------------------------------ preferences API
async def test_follow_and_unfollow_are_idempotent_and_validated(client):
    h = {"Authorization": f"Bearer {await register_and_login(client)}"}
    for _ in range(2):
        r = await client.post(
            "/api/v1/preferences/follow", headers=h, json={"type": "repository", "value": "vllm-project/vllm"}
        )
        assert r.status_code == 200
    r = await client.post(
        "/api/v1/preferences/follow", headers=h, json={"type": "repository", "value": "VLLM-project/VLLM"}
    )
    assert r.json()["followed_repositories"] == ["vllm-project/vllm"]
    await client.post(
        "/api/v1/preferences/follow", headers=h, json={"type": "provider", "value": " Anthropic "}
    )
    r = await client.post(
        "/api/v1/preferences/follow", headers=h, json={"type": "technology", "value": "Kubernetes"}
    )
    p = r.json()
    assert p["followed_providers"] == ["Anthropic"] and p["followed_technologies"] == ["Kubernetes"]
    r = await client.post(
        "/api/v1/preferences/unfollow", headers=h, json={"type": "technology", "value": "kubernetes"}
    )
    assert r.json()["followed_technologies"] == []
    r = await client.post(
        "/api/v1/preferences/unfollow", headers=h, json={"type": "technology", "value": "kubernetes"}
    )
    assert r.status_code == 200
    for bad in ({"type": "repository", "value": "not-a-repo"}, {"type": "team", "value": "x"},
                {"type": "technology", "value": "   "}, {"type": "technology", "value": "x" * 101}):  # fmt: skip
        assert (await client.post("/api/v1/preferences/follow", headers=h, json=bad)).status_code == 422, bad
    assert (
        await client.post("/api/v1/preferences/follow", json={"type": "provider", "value": "x"})
    ).status_code == 401


async def test_notification_preferences_round_trip(client):
    h = {"Authorization": f"Bearer {await register_and_login(client)}"}
    p = (await client.get("/api/v1/preferences", headers=h)).json()
    a = p["alert_settings"]
    assert a["model_releases"] and a["briefing_ready"] and a["model_providers"] == []
    assert p["briefing_weekday"] == 0
    r = await client.put(
        "/api/v1/preferences",
        headers=h,
        json={
            "briefing_frequency": "weekly",
            "briefing_weekday": 4,
            "briefing_hour": 18,
            "timezone": "Europe/Paris",
            "min_notification_severity": "critical",
            "alert_settings": {
                **a,
                "model_releases": False,
                "model_providers": ["Google"],
                "briefing_ready": False,
            },
        },
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["briefing_weekday"] == 4 and p["briefing_frequency"] == "weekly"
    assert p["alert_settings"]["model_providers"] == ["Google"] and not p["alert_settings"]["briefing_ready"]
    assert (
        await client.put("/api/v1/preferences", headers=h, json={"briefing_weekday": 7})
    ).status_code == 422


# ------------------------------------------------------------------ notifications API
async def test_notification_center_filters_unread_and_delete(client, session_factory):
    h = {"Authorization": f"Bearer {await register_and_login(client)}"}
    h2 = {"Authorization": f"Bearer {await register_and_login(client, 'other@example.com')}"}
    async with session_factory() as s:
        uid = await s.scalar(select(User.id).where(User.email == "user@example.com"))
        for i, (kind, sev) in enumerate(
            [
                (NotificationKind.CRITICAL_ALERT, Severity.CRITICAL),
                (NotificationKind.MODEL_RELEASE, Severity.INFO),
                (NotificationKind.VULNERABILITY, Severity.HIGH),
                (NotificationKind.BRIEFING, Severity.INFO),
            ]
        ):
            s.add(Notification(user_id=uid, kind=kind, severity=sev, title=f"n{i}", dedup_key=f"k{i}",
                               created_at=NOW - timedelta(minutes=i)))  # fmt: skip
        await s.commit()
    c = (await client.get("/api/v1/notifications/unread-count", headers=h)).json()
    assert c["unread"] == 4 and c["by_kind"]["model_release"] == 1
    r = await client.get(
        "/api/v1/notifications", headers=h, params={"kind": ["vulnerability", "critical_alert"]}
    )
    assert [n["title"] for n in r.json()["items"]] == ["n0", "n2"]
    r = await client.get("/api/v1/notifications", headers=h, params={"severity": "info"})
    assert r.json()["total"] == 2
    assert (await client.get("/api/v1/notifications", headers=h, params={"bogus": 1})).status_code == 422
    nid = r.json()["items"][0]["id"]
    assert (
        await client.post(f"/api/v1/notifications/{nid}/read", headers=h2)
    ).status_code == 404  # not yours
    assert (await client.post(f"/api/v1/notifications/{nid}/read", headers=h)).status_code == 204
    assert (await client.post(f"/api/v1/notifications/{nid}/unread", headers=h)).status_code == 204
    assert (await client.get("/api/v1/notifications/unread-count", headers=h)).json()["unread"] == 4
    r = await client.post("/api/v1/notifications/read-all", headers=h, params={"kind": "model_release"})
    assert r.status_code == 204
    c = (await client.get("/api/v1/notifications/unread-count", headers=h)).json()
    assert c["unread"] == 3 and "model_release" not in c["by_kind"]
    assert (await client.delete(f"/api/v1/notifications/{nid}", headers=h2)).status_code == 404
    assert (await client.delete(f"/api/v1/notifications/{nid}", headers=h)).status_code == 204
    assert (await client.delete(f"/api/v1/notifications/{nid}", headers=h)).status_code == 404
    r = await client.get("/api/v1/notifications", headers=h)
    assert r.json()["total"] == 3 and nid not in [n["id"] for n in r.json()["items"]]
    async with session_factory() as s:  # the dedup key survives deletion, so the event never comes back
        assert (
            await s.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == uid))
            == 4
        )


async def test_deleted_alert_is_not_redelivered(session_factory, intel, client):
    h = {"Authorization": f"Bearer {await register_and_login(client)}"}
    async with session_factory() as s:
        await AlertEngine(s, NOW).run()
        await s.commit()
    items = (await client.get("/api/v1/notifications", headers=h, params={"kind": "model_release"})).json()[
        "items"
    ]
    assert len(items) == 1
    await client.delete(f"/api/v1/notifications/{items[0]['id']}", headers=h)
    async with session_factory() as s:
        stats = await AlertEngine(s, NOW + timedelta(minutes=5)).run()
        await s.commit()
    assert stats.created == 0
    assert (await client.get("/api/v1/notifications", headers=h, params={"kind": "model_release"})).json()[
        "total"
    ] == 0


def test_briefing_task_retry_policy():
    from app.workers.celery_app import celery_app
    from app.workers.tasks import generate_briefing

    assert generate_briefing.max_retries == 3 and generate_briefing.autoretry_for == (Exception,)
    sched = celery_app.conf.beat_schedule
    assert sched["briefings"]["schedule"] == 300.0 and sched["alerts"]["schedule"] == 300.0
