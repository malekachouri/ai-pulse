import uuid
from datetime import UTC, date, datetime, timedelta

from app.models import AIAnalysis, DailyBriefing, Notification
from app.models.enums import AnalysisKind, NotificationKind, Severity
from tests.conftest import register_and_login


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _user_id(client, token) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/auth/me", headers=_h(token))).json()["id"])


async def test_catalog(client, seeded):
    cats = (await client.get("/api/v1/categories")).json()
    assert len(cats) == 15 and {"slug", "name", "id"} <= set(cats[0])
    sources = (await client.get("/api/v1/sources")).json()
    assert [s["slug"] for s in sources] == ["test-feed"]


async def test_bookmarks_flow(client, seeded):
    assert (await client.get("/api/v1/bookmarks")).status_code == 401
    h = _h(await register_and_login(client))
    a1 = seeded["a1"]
    assert (await client.put(f"/api/v1/bookmarks/{a1}", headers=h)).status_code == 204
    assert (await client.put(f"/api/v1/bookmarks/{a1}", headers=h)).status_code == 204  # idempotent
    r = await client.put(f"/api/v1/bookmarks/{a1}", json={"note": "read later"}, headers=h)
    assert r.status_code == 204
    assert (await client.put(f"/api/v1/bookmarks/{uuid.uuid4()}", headers=h)).status_code == 404

    page = (await client.get("/api/v1/bookmarks", headers=h)).json()
    assert page["total"] == 1
    assert page["items"][0]["note"] == "read later"
    assert page["items"][0]["article"]["is_bookmarked"] is True
    news = (await client.get("/api/v1/news", headers=h)).json()["items"]
    assert {i["id"]: i["is_bookmarked"] for i in news}[str(a1)] is True

    assert (await client.delete(f"/api/v1/bookmarks/{a1}", headers=h)).status_code == 204
    assert (await client.get("/api/v1/bookmarks", headers=h)).json()["total"] == 0


async def test_bookmarks_are_private(client, seeded):
    h1 = _h(await register_and_login(client, "one@example.com"))
    await client.put(f"/api/v1/bookmarks/{seeded['a1']}", headers=h1)
    h2 = _h(await register_and_login(client, "two@example.com"))
    assert (await client.get("/api/v1/bookmarks", headers=h2)).json()["total"] == 0


async def test_notifications(client, session_factory):
    token = await register_and_login(client)
    h = _h(token)
    uid = await _user_id(client, token)
    other = _h(await register_and_login(client, "other@example.com"))
    now = datetime.now(UTC)
    async with session_factory() as s:
        for i in range(3):
            s.add(
                Notification(
                    user_id=uid,
                    kind=NotificationKind.VULNERABILITY,
                    severity=Severity.HIGH,
                    title=f"n{i}",
                    dedup_key=f"k{i}",
                    created_at=now - timedelta(minutes=i),
                )
            )
        await s.commit()

    assert (await client.get("/api/v1/notifications/unread-count", headers=h)).json()["unread"] == 3
    items = (await client.get("/api/v1/notifications", headers=h)).json()["items"]
    assert [n["title"] for n in items] == ["n0", "n1", "n2"]
    nid = items[0]["id"]
    assert (await client.post(f"/api/v1/notifications/{nid}/read", headers=other)).status_code == 404
    assert (await client.post(f"/api/v1/notifications/{nid}/read", headers=h)).status_code == 204
    r = await client.get("/api/v1/notifications", params={"unread_only": True}, headers=h)
    assert r.json()["total"] == 2
    assert (await client.post("/api/v1/notifications/read-all", headers=h)).status_code == 204
    assert (await client.get("/api/v1/notifications/unread-count", headers=h)).json() == {
        "unread": 0,
        "by_kind": {},
    }


async def test_preferences(client):
    h = _h(await register_and_login(client))
    p = (await client.get("/api/v1/preferences", headers=h)).json()
    assert p["briefing_frequency"] == "daily" and p["timezone"] == "UTC"
    r = await client.put(
        "/api/v1/preferences",
        json={
            "interests": ["rag", "kubernetes", "rag"],
            "followed_repositories": ["vllm-project/vllm", " vllm-project/vllm "],
            "timezone": "Europe/Paris",
            "briefing_hour": 8,
            "min_notification_severity": "critical",
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["interests"] == ["rag", "kubernetes"]
    assert p["followed_repositories"] == ["vllm-project/vllm"]
    assert p["timezone"] == "Europe/Paris" and p["briefing_hour"] == 8
    for bad in ({"interests": ["astrology"]}, {"timezone": "Mars/Base"}, {"briefing_hour": 24},
                {"followed_repositories": ["noslash"]}, {"theme": "neon"}):  # fmt: skip
        assert (await client.put("/api/v1/preferences", json=bad, headers=h)).status_code == 422, bad


async def test_briefings_empty_and_personalised(client, session_factory):
    r = await client.get("/api/v1/briefings/latest")
    assert r.status_code == 404 and "No briefing" in r.json()["error"]["message"]

    token = await register_and_login(client)
    uid = await _user_id(client, token)
    now = datetime.now(UTC)
    today = date.today()
    async with session_factory() as s:
        for owner, summary in ((None, "global"), (uid, "mine")):
            s.add(
                DailyBriefing(
                    user_id=owner,
                    briefing_date=today,
                    period_start=now - timedelta(days=1),
                    period_end=now,
                    executive_summary=summary,
                    sections={},
                    cited_article_ids=[],
                    generated_at=now,
                )
            )
        await s.commit()
    assert (await client.get("/api/v1/briefings/latest")).json()["executive_summary"] == "global"
    mine = await client.get("/api/v1/briefings/latest", headers=_h(token))
    assert mine.json()["executive_summary"] == "mine"
    listed = (await client.get("/api/v1/briefings", headers=_h(token))).json()
    assert [b["personalized"] for b in listed] == [True, False]
    other = _h(await register_and_login(client, "nosy@example.com"))
    r = await client.get(f"/api/v1/briefings/{today.isoformat()}", headers=other)
    assert r.json()["executive_summary"] == "global"


async def test_ai_summary_attached_only_when_valid(client, session_factory, seeded):
    now = datetime.now(UTC)
    async with session_factory() as s:
        s.add_all([
            AIAnalysis(article_id=seeded["a1"], kind=AnalysisKind.SUMMARY, prompt_version="v1",
                       provider="ollama", model="llama3", output={"short_summary": "Short text."},
                       created_at=now),
            AIAnalysis(article_id=seeded["a2"], kind=AnalysisKind.SUMMARY, prompt_version="v1",
                       provider="ollama", model="llama3", output={"short_summary": "Bad"}, valid=False,
                       created_at=now),
        ])  # fmt: skip
        await s.commit()
    items = {i["id"]: i for i in (await client.get("/api/v1/news")).json()["items"]}
    s1 = items[str(seeded["a1"])]["ai_summary"]
    assert s1["short"] == "Short text." and s1["provider"] == "ollama"
    assert items[str(seeded["a2"])]["ai_summary"] is None


async def test_dashboard_extended_fields(client, seeded):
    d = (await client.get("/api/v1/dashboard/summary")).json()
    assert {"key": "critical", "count": 1} in d["by_severity"]
    assert {t["key"] for t in d["trending_tags"]} == {"rag", "evaluation"}
    assert [a["id"] for a in d["latest_ai"]] == [str(seeded["a1"])]
    assert d["recent_failures"] == []
