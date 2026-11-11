"""Recommendations (rule-based, explained) and the Learning Assistant (AI lessons, grounded, curated links)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.ai.learning import CATALOG
from app.ai.lessons import LessonGenerator, LessonsDisabledError
from app.ai.pipeline import AnalysisPipeline
from app.models import Article, Category, LearningLesson, Role, Source, User, UserPreference
from app.models.enums import ItemType, SourceType, VerificationStatus
from tests.ai_fakes import ScriptedChat, providers
from tests.conftest import register_and_login

NOW = datetime.now(UTC)
CURATED = {url for links in CATALOG.values() for _, url in links}
LEARN = "/api/v1/learning"

ITEMS = {
    # key: (type, title, description, categories, hours ago)
    "vllm": (ItemType.NEWS, "vLLM adds speculative decoding for faster LLM serving",
             "The vLLM project ships speculative decoding.", ["llmops"], 3),
    "kv-read": (ItemType.NEWS, "Paged attention and KV cache memory explained for LLM serving",
                "How paged attention manages the kv cache memory of transformer inference.", ["llmops"], 30),
    "kv-similar": (ItemType.RESEARCH, "Compressing the KV cache memory with paged attention",
                   "A paper on kv cache memory compression and paged attention for inference.", ["ai-research"], 5),
    "rag": (ItemType.NEWS, "A retrieval evaluation toolkit for RAG pipelines",
            "Evaluate retrieval quality in RAG systems.", ["rag"], 6),
    "cloud": (ItemType.DEVOPS, "Object storage pricing update",
              "New storage tiers for archives.", ["cloud"], 2),
}  # fmt: skip


@pytest.fixture
async def items(session_factory):
    async with session_factory() as s:
        src = Source(slug="learn-src", name="Learning test source", source_type=SourceType.RSS, connector="rss",
                     url="https://t.test/feed", default_item_type=ItemType.NEWS, is_official=True, reliability=0.9)  # fmt: skip
        s.add(src)
        await s.flush()
        cats = {c.slug: c for c in await s.scalars(select(Category))}
        ids = {}
        for key, (t, title, desc, cs, hours) in ITEMS.items():
            a = Article(source_id=src.id, external_id=key, item_type=t, title=title, description=desc,
                        url=f"https://t.test/{key}", published_at=NOW - timedelta(hours=hours),
                        collected_at=NOW - timedelta(hours=hours), content_hash=key.ljust(64, "x"),
                        verification_status=VerificationStatus.OFFICIAL, categories=[cats[c] for c in cs])  # fmt: skip
            s.add(a)
            await s.flush()
            ids[key] = a.id
        await s.commit()
        await AnalysisPipeline(s, providers()).run()  # keywords and importance, like production
        await s.commit()
    return ids


async def _user(s, email, followed=()):
    user = User(email=email, password_hash="x", role=await s.scalar(select(Role).where(Role.name == "user")))
    s.add(user)
    await s.flush()
    s.add(UserPreference(user_id=user.id, followed_technologies=list(followed)))
    await s.flush()
    return user


async def _reader(client, email="learner@example.com"):
    h = {"Authorization": f"Bearer {await register_and_login(client, email)}"}
    r = await client.put(
        "/api/v1/preferences", headers=h, json={"followed_technologies": ["vLLM"], "interests": ["rag"]}
    )
    assert r.status_code == 200
    return h


async def test_recommendations_are_explained_and_personal(client, items):
    h = await _reader(client)
    assert (await client.put(f"/api/v1/news/{items['kv-read']}/read", headers=h)).status_code in (200, 204)

    r = await client.get(f"{LEARN}/recommendations", headers=h)
    assert r.status_code == 200
    body = r.json()
    recs = {i["article"]["url"].rsplit("/", 1)[-1]: i["reasons"] for i in body["items"]}
    assert recs["vllm"] == ["Because you follow vLLM"]
    assert any(x.startswith("Because you read “Paged attention and KV cache") and "shared:" in x
               for x in recs["kv-similar"])  # fmt: skip
    assert recs["rag"] == ["Matches your interest in RAG"]
    assert "kv-read" not in recs  # already read
    assert "cloud" not in recs  # nothing personal about it: left to the regular feeds
    assert body["signals"] == {"followed": ["vLLM"], "interests": ["rag"], "read": 1, "bookmarked": 0}

    # Only collected items and curated documentation.
    assert all(i["article"]["url"].startswith("https://t.test/") for i in body["items"])
    assert body["resources"] and {x["url"] for x in body["resources"]} <= CURATED
    vllm_doc = next(x for x in body["resources"] if x["title"] == "vLLM documentation")
    assert vllm_doc["reason"] == "Because you follow vLLM"


async def test_bookmarks_count_as_a_signal_and_new_users_get_guidance(client, items):
    h = {"Authorization": f"Bearer {await register_and_login(client, 'fresh@example.com')}"}
    r = (await client.get(f"{LEARN}/recommendations", headers=h)).json()
    assert r["items"] == [] and "Follow technologies" in r["note"]

    assert (await client.put(f"/api/v1/bookmarks/{items['kv-read']}", headers=h)).status_code in (
        200,
        201,
        204,
    )
    r = (await client.get(f"{LEARN}/recommendations", headers=h)).json()
    reasons = {i["article"]["url"].rsplit("/", 1)[-1]: i["reasons"] for i in r["items"]}
    assert any("Because you bookmarked" in x for x in reasons["kv-similar"])
    assert (await client.get(f"{LEARN}/recommendations")).status_code == 401


def _lesson(**over):
    return {
        "title": "How speculative decoding speeds up LLM serving",
        "explanation": "A small draft model proposes tokens that the large model verifies in one pass.",
        "key_points": ["Draft tokens are verified in parallel", "It is 47% faster in all cases"],
        "why_it_matters": "Serving latency drops without changing outputs.",
        "try_it": "Enable speculative decoding in a test deployment.",
        "topics": ["llmops", "made-up-topic"],
        **over,
    }


async def test_lessons_are_grounded_personal_and_link_only_curated_docs(session_factory, items):
    async with session_factory() as s:
        user = await _user(s, "lessons@example.com", ["vLLM"])
        chat = ScriptedChat(default=_lesson())
        lessons = await LessonGenerator(s, providers(chat=chat), NOW).generate(user)
        await s.commit()

    assert len(lessons) == 3 and len(chat.calls) == 3
    first = lessons[0].content
    assert first["source"]["url"] == "https://t.test/vllm"  # what the user follows comes first
    assert first["personal_reason"] == "Because you follow vLLM"
    assert "It is 47% faster in all cases" not in first["key_points"]  # unsupported number removed
    assert "47%" in first["unsupported_claims_removed"]
    assert first["topics"] == ["llmops"]  # only catalog topics
    assert first["resources"] and all(r["url"] in CURATED for r in first["resources"])
    assert first["ai_generated"] is True and lessons[0].provider == "fake"
    assert "vLLM" in chat.calls[0]["user"] and "Allowed topics:" in chat.calls[0]["user"]


async def test_lessons_api_states_and_generation(client, session_factory, items):
    h = await _reader(client, "lessons-api@example.com")
    r = await client.get(f"{LEARN}/lessons", headers=h)
    assert r.json()["status"] == "disabled" and r.json()["lessons"] == []
    assert (await client.post(f"{LEARN}/lessons/generate", headers=h)).status_code == 400

    client._transport.app.state.ai_providers = providers(chat=ScriptedChat(default=_lesson()))  # type: ignore[attr-defined]
    r = await client.post(f"{LEARN}/lessons/generate", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert (
        body["status"] == "ready"
        and len(body["lessons"]) == 3
        and "AI-generated" in body["ai_generated_notice"]
    )
    again = (await client.get(f"{LEARN}/lessons", headers=h)).json()
    assert [x["id"] for x in again["lessons"]] == [x["id"] for x in body["lessons"]]
    async with session_factory() as s:
        assert len((await s.scalars(select(LearningLesson))).all()) == 3


async def test_no_llm_no_lessons(session_factory, items):
    async with session_factory() as s:
        with pytest.raises(LessonsDisabledError):
            await LessonGenerator(s, providers(), NOW).generate(
                User(email="x@example.com", password_hash="x")
            )


async def test_a_lesson_whose_core_is_unsupported_is_dropped(session_factory, items):
    async with session_factory() as s:
        user = await _user(s, "dropped@example.com")
        bad = _lesson(explanation="Version 9.9.9 cut latency by 83%.")
        out = await LessonGenerator(s, providers(chat=ScriptedChat(default=bad)), NOW).generate(user)
    assert out == []
