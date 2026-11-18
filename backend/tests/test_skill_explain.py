"""'What is it good for?': general, from the tool's own sources only, cited, stored, honest when silent."""

import httpx
from sqlalchemy import select

from app.ai.providers import ProviderError
from app.models import AISkill, AIUsage
from app.models.enums import SkillKind
from app.skills.explain import INSUFFICIENT, clean_readme, readme_url
from tests import feature_data as fd
from tests.ai_fakes import ScriptedChat, providers
from tests.conftest import register_and_login
from tests.ingestion_helpers import MockHttp

README = "https://raw.githubusercontent.com/acme/pg-mcp/HEAD/README.md"
README_TEXT = """# pg-mcp
<!-- hidden note -->
![build](https://img.shields.io/badge/build-passing.svg)
Read-only SQL for PostgreSQL 16 and 17. Connect with a role that cannot write.

Configure DATABASE_URL and run `npx -y pg-mcp@0.2.0`.
"""


async def _skill(session_factory, **kw):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        src = await fd.source(s, "reg", connector="mcp_registry", name="Official MCP Registry")
        row = AISkill(source_id=src.id, kind=SkillKind.MCP_SERVER, name="io.github.acme/pg-mcp", title="pg-mcp",
                      description="Query PostgreSQL databases from an AI assistant.", version="0.2.0",
                      listing_url="https://registry.test/pg-mcp", repository_url="https://github.com/acme/pg-mcp",
                      first_seen_at=fd.NOW, last_seen_at=fd.NOW, stack_tags=["postgresql"],
                      install=[{"label": "Run locally from npm", "notes": ["Set DATABASE_URL (secret)"],
                                "command": "claude mcp add pg-mcp -- npx -y pg-mcp@0.2.0"}], **kw)  # fmt: skip
        s.add(row)
        await s.commit()
        return row.id


def _setup(client, chat, readme=httpx.Response(200, text=README_TEXT)):  # type: ignore[no-untyped-def]
    mock = MockHttp({README: readme})
    state = client._transport.app.state  # type: ignore[attr-defined]
    state.ai_providers = providers(chat=chat)
    state.skill_http = mock.client()
    return mock


REPLY = {
    "what_it_does": {"text": "It runs read-only SQL against PostgreSQL 16 and 17.", "citations": [1, 2]},
    "use_cases": {
        "text": "It suits any project that stores data in PostgreSQL and wants an assistant to inspect "
        "tables while debugging. It also speeds queries up by 40%.",
        "citations": [2, 1],
    },  # fmt: skip
    "how_to_try": {
        "text": "Add it with claude mcp add and npx pg-mcp@0.2.0.",
        "citations": [3],
    },  # no source 3
    "cautions": {"text": "Use a database role that cannot write.", "citations": [2, 99]},
}


async def test_explanation_is_grounded_cited_and_stored(client, session_factory):
    sid = await _skill(session_factory)
    chat = ScriptedChat(default=REPLY)
    mock = _setup(client, chat)
    anon = await client.post(f"/api/v1/skills/{sid}/explanation")
    assert anon.status_code == 401
    before = (await client.get(f"/api/v1/skills/{sid}/explanation")).json()
    assert before == {**before, "status": "none", "sections": None, "llm_available": True}

    h = {"Authorization": f"Bearer {await register_and_login(client, 'skills@example.com')}"}
    r = await client.post(f"/api/v1/skills/{sid}/explanation", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ready" and out["ai_generated"] is True and out["provider"] == "fake"
    assert out["listing_version"] == "0.2.0"
    assert [(s["n"], s["kind"], s["url"]) for s in out["sources"]] == [
        (1, "listing", "https://registry.test/pg-mcp"),
        (2, "readme", "https://github.com/acme/pg-mcp"),
    ]
    sec = out["sections"]
    assert sec["what_it_does"] == {
        "text": REPLY["what_it_does"]["text"],
        "insufficient": False,
        "citations": [1, 2],
        "citations_matched": False,
        "reason": None,
    }
    # General use cases from the tool's sources; the invented 40% is removed with its sentence.
    assert sec["use_cases"]["text"].startswith("It suits any project that stores data in PostgreSQL")
    assert "40%" not in sec["use_cases"]["text"] and out["unsupported_claims_removed"] == ["40%"]
    assert sec["use_cases"]["citations"] == [2, 1]
    # Cited a source that does not exist: matched instead to the listing, which holds the command.
    assert sec["how_to_try"]["citations"] == [1] and sec["how_to_try"]["citations_matched"] is True
    assert sec["cautions"]["citations"] == [2]  # unknown source 99 dropped

    prompt = chat.calls[0]["user"]
    assert "Read-only SQL for PostgreSQL 16" in prompt and "AI Pulse" not in prompt  # not tied to one project
    assert "hidden note" not in prompt and "shields.io" not in prompt  # README cleaned
    assert [str(r.url) for r in mock.requests] == [README]

    # Stored and served from then on; the list says when it was explained.
    again = (await client.get(f"/api/v1/skills/{sid}/explanation")).json()
    assert again["sections"] == sec and again["generated_at"] == out["generated_at"]
    listed = (await client.get("/api/v1/skills", params={"days": 7})).json()["items"][0]
    assert listed["explained_at"] is not None
    async with session_factory() as s:
        usage = await s.scalar(select(AIUsage).where(AIUsage.purpose == "skill_explain"))
        assert usage is not None and usage.ok


async def test_without_readme_without_llm_and_on_model_errors(client, session_factory):
    sid = await _skill(session_factory)
    h = {"Authorization": f"Bearer {await register_and_login(client, 'skills2@example.com')}"}

    nothing = {"text": None, "citations": []}
    silent = {"what_it_does": nothing, "how_to_try": nothing, "cautions": nothing,
              "use_cases": {"text": "It suits data projects.", "citations": [2]}}  # [2] is the absent README  # fmt: skip
    _setup(client, ScriptedChat(default=silent), readme=httpx.Response(404))
    out = (await client.post(f"/api/v1/skills/{sid}/explanation", headers=h)).json()
    assert [s["kind"] for s in out["sources"]] == ["listing"]  # no README: [2] is absent
    assert out["status"] == "insufficient"
    sec = out["sections"]
    assert all(v["text"] == INSUFFICIENT and v["insufficient"] and not v["citations"] for v in sec.values())
    assert sec["use_cases"]["reason"] == "the model's text matches no source"  # and no README to match
    assert sec["cautions"]["reason"] == "the model wrote nothing for this section"

    _setup(client, ScriptedChat([ProviderError("model timed out", retryable=True)] * 3))
    failed = (await client.post(f"/api/v1/skills/{sid}/explanation", headers=h)).json()
    assert failed["status"] == "failed" and "timed out" in failed["error"]
    kept = (await client.get(f"/api/v1/skills/{sid}/explanation")).json()
    assert kept["status"] == "insufficient"  # the previous explanation stays
    async with session_factory() as s:
        oks = list(await s.scalars(select(AIUsage.ok).where(AIUsage.purpose == "skill_explain")))
        assert oks.count(False) >= 1

    client._transport.app.state.ai_providers = providers()  # type: ignore[attr-defined]
    no_llm = await client.post(f"/api/v1/skills/{sid}/explanation", headers=h)
    assert no_llm.status_code == 400 and "LLM" in no_llm.text
    assert (await client.get(f"/api/v1/skills/{sid}/explanation")).json()["llm_available"] is False
    missing = "/api/v1/skills/00000000-0000-0000-0000-000000000001/explanation"
    assert (await client.post(missing, headers=h)).status_code == 404


def test_readme_location_and_cleanup():
    assert readme_url("https://github.com/acme/pg-mcp") == README
    assert readme_url("https://github.com/acme/pg-mcp.git") == README
    assert readme_url("https://gitlab.com/acme/pg-mcp") is None and readme_url(None) is None
    assert readme_url("https://github.com/acme/pg-mcp/tree/main/sub") is None
    assert clean_readme("a<b>bold</b>\n\n\n\n![x](y.png)c") == "abold\n\nc"
    assert len(clean_readme("x" * 10_000)) == 6000


async def test_small_models_that_do_not_cite(client, session_factory):
    """qwen2.5:3b-like replies: right text, empty citations. Matched to the sources holding its words."""
    sid = await _skill(session_factory)
    h = {"Authorization": f"Bearer {await register_and_login(client, 'skills3@example.com')}"}
    reply = {
        "what_it_does": {"text": "Query PostgreSQL databases from an AI assistant.", "citations": []},
        "use_cases": {"text": "Read-only SQL for PostgreSQL in projects with a role that cannot write.",
                      "citations": []},
        "how_to_try": {"text": "Bake a chocolate cake with fresh strawberries tonight.", "citations": []},
        "cautions": {"text": "Set DATABASE_URL with a role that cannot write.", "citations": []},
    }  # fmt: skip
    _setup(client, ScriptedChat(default=reply))
    out = (await client.post(f"/api/v1/skills/{sid}/explanation", headers=h)).json()
    sec = out["sections"]
    assert out["status"] == "ready"
    assert sec["what_it_does"]["citations"] == [1] and sec["what_it_does"]["citations_matched"] is True
    assert (
        sec["use_cases"]["citations"] == [2] and sec["use_cases"]["citations_matched"] is True
    )  # README words
    assert (
        sec["how_to_try"]["insufficient"]
        and sec["how_to_try"]["reason"] == "the model's text matches no source"
    )
    assert 2 in sec["cautions"]["citations"]


def test_reply_schema_requires_every_section():
    """With a JSON-schema constrained reply (Ollama), optional fields let a small model leave sections out."""
    from app.ai.providers.base import json_schema
    from app.skills.explain import SkillExplanation

    schema = json_schema(SkillExplanation)
    assert set(schema["required"]) == {"what_it_does", "use_cases", "how_to_try", "cautions"}
    part = schema["$defs"]["Part"] if "$defs" in schema else schema["definitions"]["Part"]
    assert set(part["required"]) == {"text", "citations"}
