"""Skills radar connectors against trimmed real responses (MCP Registry and Anthropic's marketplaces, captured
2026-11-15): entries, install commands built from the listing, resumable paging, removals, baselines."""

from datetime import timedelta

import httpx
from sqlalchemy import select

from app.models import AISkill, Article, Source
from app.models.enums import JobStatus, SkillKind
from app.skills import frontmatter
from app.skills.stack import stack_tags
from tests.ingestion_helpers import NOW, MockHttp, fixture_bytes, fixture_json, ingest, js, make_source

REGISTRY = "https://registry.test"
RAW = "https://raw.test"


async def _skills(sf, source_id):  # type: ignore[no-untyped-def]
    async with sf() as s:
        rows = await s.scalars(select(AISkill).where(AISkill.source_id == source_id).order_by(AISkill.name))
        return {r.name: r for r in rows}


def _registry(pages: dict[str | None, dict], seen: list[dict]):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen.append(params)
        return js(pages[params.get("cursor")])

    return handler


# ------------------------------------------------------------------------------------------- MCP Registry
async def test_mcp_registry_entries_and_install_commands(session_factory):
    sid = await make_source(session_factory, "mcp_registry", REGISTRY, default_item_type="tool")
    seen: list[dict] = []
    pages = {None: fixture_json("mcp_registry_page1.json"),
             "com.devart/mcp-postgresql:1.0.0": fixture_json("mcp_registry_page2.json")}  # fmt: skip
    job = await ingest(session_factory, sid, MockHttp({f"{REGISTRY}/v0/servers": _registry(pages, seen)}))
    assert job.status == JobStatus.SUCCEEDED and job.items_created == 5

    first = seen[0]
    assert first["version"] == "latest" and first["limit"] == "100" and "cursor" not in first
    assert first["updated_since"] == (NOW - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    assert seen[1]["cursor"] == "com.devart/mcp-postgresql:1.0.0"

    rows = await _skills(session_factory, sid)
    hosted = rows["ad.tributs/mcp"]
    assert hosted.kind == SkillKind.MCP_SERVER and hosted.version == "1.0.0" and hosted.initial is False
    assert hosted.publisher == "ad.tributs" and hosted.homepage_url == "https://tributs.ad/en/ai"
    assert hosted.listing_url == f"{REGISTRY}/v0/servers/ad.tributs%2Fmcp/versions/latest"
    assert hosted.published_at and hosted.published_at.isoformat().startswith("2026-11-14T10:27:16")
    assert [i["command"] for i in hosted.install] == [
        "claude mcp add --transport http mcp https://mcp.tributs.ad/mcp"
    ]

    pg = rows["io.github.Eszetael/postgres-mcp-hardened"]
    assert pg.repository_url and "postgresql" in pg.stack_tags
    assert "github" not in pg.stack_tags  # "io.github.<user>/" is where it is published, not what it does
    npm, oci = pg.install
    assert npm["command"] == (
        "claude mcp add postgres-mcp-hardened -e 'DATABASE_URL=<DATABASE_URL>' -- "
        "npx -y --stdio postgres-mcp-hardened@0.1.10"
    )  # the listing's runtime argument, in the place the server.json schema gives it
    assert npm["notes"][0].startswith("Set DATABASE_URL (secret): Connection string")
    assert any(n.startswith("Optional settings: MCP_STATEMENT_TIMEOUT") for n in npm["notes"])
    assert oci["command"] == (
        "docker run -i --rm -e DATABASE_URL ghcr.io/eszetael/postgres-mcp-hardened:0.1.10\n"
        "claude mcp add --transport http postgres-mcp-hardened http://localhost:8080/mcp"
    )
    assert pg.facts["packages"][0] == {"registryType": "npm", "identifier": "postgres-mcp-hardened",
                                       "version": "0.1.10", "runtimeHint": "npx", "transport": "stdio"}  # fmt: skip

    assert rows["io.github.AIops-tools/postgres-aiops"].install[0]["command"] == (
        "claude mcp add postgres-aiops -- uvx postgres-aiops==0.13.0"
    )
    devart = rows["com.devart/mcp-postgresql"].install[0]["command"]
    assert devart.startswith("claude mcp add mcp-postgresql -e 'DEVART_MCP_POSTGRESQL_CONNECTION=<")
    assert devart.endswith("-- dnx Devart.Mcp.PostgreSql@1.1.0 run")

    ugt = rows["com.usegithubthing/ugt"].install
    assert ugt[0]["label"].startswith("Connect to the hosted server") and len(ugt) == 7
    assert (
        all(i["command"].endswith(".mcpb") for i in ugt[1:])
        and "github" in rows["com.usegithubthing/ugt"].stack_tags
    )

    async with session_factory() as s:
        src = await s.get(Source, sid)
        assert src.checkpoint == {
            "updated_since": (NOW - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        }
        assert await s.scalar(select(Article.id)) is None  # the radar never writes articles


async def test_mcp_registry_resumes_paging_and_updates_in_place(session_factory):
    sid = await make_source(session_factory, "mcp_registry", REGISTRY, default_item_type="tool",
                            config={"max_pages": 1})  # fmt: skip
    seen: list[dict] = []
    page1, page2 = fixture_json("mcp_registry_page1.json"), fixture_json("mcp_registry_page2.json")
    mock = MockHttp(
        {f"{REGISTRY}/v0/servers": _registry({None: page1, page1["metadata"]["nextCursor"]: page2}, seen)}
    )
    await ingest(session_factory, sid, mock)
    async with session_factory() as s:
        cp = (await s.get(Source, sid)).checkpoint
    assert cp["cursor"] == "com.devart/mcp-postgresql:1.0.0" and len(await _skills(session_factory, sid)) == 4

    later = NOW + timedelta(hours=1)
    await ingest(session_factory, sid, mock, now=later)  # same window, from the cursor
    assert seen[1]["cursor"] == cp["cursor"] and seen[1]["updated_since"] == cp["updated_since"]
    async with session_factory() as s:
        cp2 = (await s.get(Source, sid)).checkpoint
    assert cp2 == {
        "updated_since": cp["run_started"].replace("+00:00", "Z")
    }  # done: next window starts there
    assert len(await _skills(session_factory, sid)) == 5

    # A new version of a known server updates its row; first-seen stays.
    bumped = fixture_json("mcp_registry_page2.json")
    bumped["servers"][0]["server"]["version"] = "0.4.0"
    before = (await _skills(session_factory, sid))["com.usegithubthing/ugt"].first_seen_at
    job = await ingest(session_factory, sid, MockHttp({f"{REGISTRY}/v0/servers": js(bumped)}),
                       now=later + timedelta(hours=1))  # fmt: skip
    row = (await _skills(session_factory, sid))["com.usegithubthing/ugt"]
    assert job.items_updated == 1 and job.items_created == 0
    assert row.version == "0.4.0" and row.first_seen_at == before and row.last_seen_at > before


async def test_mcp_registry_bad_entry_and_outage(session_factory):
    sid = await make_source(session_factory, "mcp_registry", REGISTRY, default_item_type="tool")
    page = fixture_json("mcp_registry_page2.json")
    page["servers"].append({"server": {"description": "no name"}})
    job = await ingest(session_factory, sid, MockHttp({f"{REGISTRY}/v0/servers": js(page)}))
    assert job.status == JobStatus.PARTIAL and job.items_created == 1
    assert job.errors[0]["stage"] == "normalize"

    down = await ingest(session_factory, sid, MockHttp({f"{REGISTRY}/v0/servers": httpx.Response(503)}))
    assert down.status == JobStatus.FAILED and "503" in down.error


# ------------------------------------------------------------------------------------- plugin marketplaces
def _market_routes(plugins: bytes | None = None) -> dict:  # type: ignore[type-arg]
    plugins_json = plugins or fixture_bytes("claude_plugins_marketplace.json")
    return {
        f"{RAW}/anthropics/claude-plugins-official/main/.claude-plugin/marketplace.json":
            httpx.Response(200, content=plugins_json),
        f"{RAW}/anthropics/skills/main/.claude-plugin/marketplace.json":
            httpx.Response(200, content=fixture_bytes("anthropic_skills_marketplace.json")),
        **{f"{RAW}/anthropics/skills/main/skills/{n}/SKILL.md": httpx.Response(200, content=fixture_bytes(f"skill_{n}.md"))
           for n in ("xlsx", "pdf", "claude-api")},
    }  # fmt: skip


async def test_marketplaces_list_plugins_and_skills(session_factory):
    config = {"marketplaces": [{"repo": "anthropics/claude-plugins-official"}, {"repo": "anthropics/skills"}]}
    sid = await make_source(
        session_factory, "claude_marketplace", RAW, default_item_type="tool", config=config
    )
    mock = MockHttp(_market_routes())
    job = await ingest(session_factory, sid, mock)
    assert job.status == JobStatus.SUCCEEDED and job.items_created == 3 + 2 + 3  # plugins, plugins, skills

    rows = await _skills(session_factory, sid)
    crunch = rows["42crunch-api-security-testing"]
    assert (
        crunch.kind == SkillKind.PLUGIN and crunch.publisher == "42Crunch" and crunch.category == "security"
    )
    assert crunch.repository_url == "https://github.com/42Crunch-AI/claude-plugins"
    assert crunch.initial is True  # listed before AI Pulse watched the marketplace: not "new"
    assert [i["command"] for i in crunch.install] == [
        "/plugin marketplace add anthropics/claude-plugins-official",
        "/plugin install 42crunch-api-security-testing@claude-plugins-official",
    ]
    assert "security" in crunch.stack_tags
    assert crunch.listing_url == (
        "https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json"
    )

    pdf = rows["pdf"]
    assert pdf.kind == SkillKind.SKILL and pdf.category == "document-skills" and pdf.facts["license"]
    assert pdf.description.startswith("Use this skill whenever the user wants to do anything with PDF files")
    assert pdf.install[1]["command"] == "/plugin install document-skills@anthropic-agent-skills"
    assert pdf.listing_url == "https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md"
    api = rows["claude-api"]  # a plugin and a skill share the name: both kept
    assert {r.kind for r in (await _skills_all(session_factory, sid, "claude-api"))} == {
        SkillKind.PLUGIN,
        SkillKind.SKILL,
    }
    assert api.description

    # Unchanged listings: nothing is read again past the marketplace files.
    n = len(mock.requests)
    again = await ingest(session_factory, sid, mock, now=NOW + timedelta(hours=6))
    assert again.status == JobStatus.SUCCEEDED and again.items_fetched == 0 and len(mock.requests) == n + 2

    # A plugin leaves the marketplace: kept, marked removed. A new one is not part of the baseline.
    data = fixture_json("claude_plugins_marketplace.json")
    data["plugins"] = [p for p in data["plugins"] if p["name"] != "adobe-for-creativity"]
    data["plugins"].append(
        {"name": "brand-new", "description": "Docker helpers", "source": "./plugins/brand-new"}
    )
    import json

    later = await ingest(session_factory, sid, MockHttp(_market_routes(json.dumps(data).encode())),
                         now=NOW + timedelta(hours=12))  # fmt: skip
    rows = await _skills(session_factory, sid)
    assert later.items_created == 1 and rows["adobe-for-creativity"].status == "removed"
    assert rows["brand-new"].initial is False and rows["brand-new"].stack_tags == ["docker"]
    assert (
        rows["brand-new"].homepage_url
        == "https://github.com/anthropics/claude-plugins-official/tree/main/plugins/brand-new"
    )


async def _skills_all(sf, source_id, name):  # type: ignore[no-untyped-def]
    async with sf() as s:
        return list(
            await s.scalars(select(AISkill).where(AISkill.source_id == source_id, AISkill.name == name))
        )


async def test_marketplace_partial_failures(session_factory):
    config = {"marketplaces": [{"repo": "anthropics/skills"}]}
    sid = await make_source(
        session_factory, "claude_marketplace", RAW, default_item_type="tool", config=config
    )
    data = fixture_json("anthropic_skills_marketplace.json")
    data["plugins"][0]["skills"] = ["./skills/xlsx", "../../../etc", "./skills/missing"]
    routes = {**_market_routes(), f"{RAW}/anthropics/skills/main/.claude-plugin/marketplace.json": js(data)}
    job = await ingest(session_factory, sid, MockHttp(routes))
    assert job.status == JobStatus.PARTIAL
    errors = " ".join(e["error"] for e in job.errors)
    assert "outside the repository" in errors and "404" in errors
    assert set(await _skills(session_factory, sid)) == {"document-skills", "claude-api", "xlsx"}

    down = await ingest(session_factory, sid, MockHttp({}), now=NOW + timedelta(hours=6))
    assert down.status == JobStatus.FAILED
    assert (await _skills(session_factory, sid))["xlsx"].status == "active"  # an outage removes nothing


# ------------------------------------------------------------------------------------------------ helpers
def test_frontmatter_reads_skill_headers():
    assert frontmatter.parse(fixture_bytes("skill_pdf.md").decode())["name"] == "pdf"
    block = frontmatter.parse(fixture_bytes("skill_claude-api.md").decode())["description"]
    assert block.startswith("Reference for the Claude API") and "\nTRIGGER" in block  # `|-` keeps lines
    quoted = frontmatter.parse(fixture_bytes("skill_xlsx.md").decode())["description"]
    assert quoted.startswith("Use this skill any time a spreadsheet") and not quoted.startswith('"')
    assert frontmatter.parse("---\nname: 'it''s'\nfolded: >\n  a\n  b\n---\n") == {
        "name": "it's",
        "folded": "a b",
    }
    assert frontmatter.parse("no front matter") == {} and frontmatter.parse("---\nname: x\n") == {}


def test_stack_tags_are_whole_word_matches():
    assert stack_tags("Query PostgreSQL and Redis from Claude Code") == ["postgresql", "redis"]
    assert stack_tags("Manage Docker containers; e2e tests with Playwright") == ["docker", "testing"]
    assert stack_tags("redistribute dockerized pythonic content") == []
    assert stack_tags(None, "") == []
