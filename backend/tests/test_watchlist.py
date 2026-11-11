"""Technology Watchlist: grouped per followed entry, whole-word matching, release notifications."""

from datetime import timedelta

from sqlalchemy import select

from app.alerts.engine import AlertEngine
from app.models import AIModel, AIModelRelease, Notification
from app.models.enums import ItemType, NotificationKind
from tests import feature_data as fd
from tests.conftest import register_and_login

FOLLOW = {
    "followed_technologies": ["vLLM", "Go"],
    "followed_providers": ["Meta"],
    "followed_repositories": ["acme/infer"],
}


async def _data(session_factory):
    async with session_factory() as s:
        src = await fd.source(s, "watch-src", name="Watch source")
        gh = await fd.source(s, "gh-src", connector="github_releases", name="GitHub releases")
        ids = {}
        ids["vllm"] = (
            await fd.article(
                s,
                src,
                "vllm",
                item_type=ItemType.TOOL,
                title="vLLM 0.9 adds speculative decoding",
                hours_ago=3,
            )
        ).id
        ids["vllm-news"] = (
            await fd.article(s, src, "vllm-news", title="Serving LLMs with vLLM at scale", hours_ago=24 * 10)
        ).id
        ids["google"] = (await fd.article(s, src, "google", title="Google ships a new TPU", hours_ago=4)).id
        ids["old"] = (await fd.article(s, src, "old", title="vLLM roadmap", hours_ago=24 * 40)).id
        ids["repo"] = (
            await fd.article(
                s,
                gh,
                "infer-v2",
                item_type=ItemType.TOOL,
                title="acme/infer v2.0",
                url="https://github.com/acme/infer/releases/tag/v2.0",
                canonical_key="gh-release:acme/infer:v2.0",
                hours_ago=5,
            )
        ).id
        llama = await fd.article(s, src, "llama", item_type=ItemType.MODEL_RELEASE, title="Llama 5 is out",
                                 hours_ago=6)  # fmt: skip
        ids["llama"] = llama.id
        m = AIModel(provider="Meta", name="Llama 5")
        s.add(m)
        await s.flush()
        s.add(AIModelRelease(model_id=m.id, article_id=llama.id, version="5", released_at=fd.NOW - timedelta(hours=6),
                             source_url=llama.url))  # fmt: skip
        await s.commit()
    return ids


async def test_watchlist_groups_followed_entries_with_sources(client, session_factory):
    ids = await _data(session_factory)
    h = {"Authorization": f"Bearer {await register_and_login(client, 'watcher@example.com')}"}
    assert (await client.put("/api/v1/preferences", headers=h, json=FOLLOW)).status_code == 200

    r = await client.get("/api/v1/watchlist", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    entries = {e["term"]: e for e in body["entries"]}
    assert set(entries) == {"vLLM", "Go", "Meta", "acme/infer"}

    vllm = entries["vLLM"]
    assert vllm["kind"] == "technology" and vllm["total"] == 2 and vllm["new_this_week"] == 1
    assert [i["id"] for i in vllm["items"]] == [
        str(ids["vllm"]),
        str(ids["vllm-news"]),
    ]  # newest first, 30 days
    assert vllm["latest_release"]["url"].endswith("/vllm")
    assert entries["Go"]["total"] == 0  # "Go" does not match "Google"
    assert entries["Meta"]["items"][0]["id"] == str(ids["llama"])  # by the provider of the tracked model
    repo = entries["acme/infer"]
    assert repo["latest_release"]["version"] == "v2.0" and repo["open_critical_bugs"] == 0
    assert all(i["url"].startswith("https://") for e in body["entries"] for i in e["items"])
    assert body["entries"][-1]["term"] == "Go"  # entries without activity last

    assert (await client.get("/api/v1/watchlist")).status_code == 401


async def test_new_user_gets_guidance(client):
    h = {"Authorization": f"Bearer {await register_and_login(client, 'empty-watch@example.com')}"}
    body = (await client.get("/api/v1/watchlist", headers=h)).json()
    assert body["entries"] == [] and "Follow technologies" in body["note"]


async def test_followed_releases_are_notified_once(session_factory):
    ids = await _data(session_factory)
    async with session_factory() as s:
        u = await fd.user(s, "notify-watch@example.com", **FOLLOW)
        off = await fd.user(s, "no-watch@example.com", **FOLLOW,
                            alert_settings={"watchlist": False, "model_releases": False})  # fmt: skip
        await s.commit()
        await AlertEngine(s, fd.NOW).run()
        await s.commit()
        again = await AlertEngine(s, fd.NOW).run()
        await s.commit()
        rows = (await s.scalars(select(Notification).where(Notification.user_id == u.id))).all()
        muted = (await s.scalars(select(Notification).where(Notification.user_id == off.id))).all()

    by_article = {n.article_id: n for n in rows}
    watch = {n.article_id for n in rows if n.kind == NotificationKind.WATCHLIST}
    assert watch == {ids["vllm"], ids["repo"]}
    assert by_article[ids["vllm"]].title.startswith("Watchlist · vLLM:")
    assert by_article[ids["repo"]].title.startswith("Watchlist · acme/infer:")
    assert by_article[ids["repo"]].link == "https://github.com/acme/infer/releases/tag/v2.0"
    # The model release is announced once, by the model-release rule, not twice.
    assert by_article[ids["llama"]].kind == NotificationKind.MODEL_RELEASE
    assert ids["google"] not in by_article and ids["vllm-news"] not in by_article
    assert again.created == 0
    assert muted == []
