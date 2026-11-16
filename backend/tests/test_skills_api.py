"""Skills radar API: filters, "new" excludes the baseline, facets, detail."""

from datetime import timedelta

from app.models import AISkill
from app.models.enums import SkillKind
from tests import feature_data as fd

NOW = fd.NOW


async def _seed(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        reg = await fd.source(s, "mcp-reg", connector="mcp_registry", name="Official MCP Registry")
        market = await fd.source(s, "plugins", connector="claude_marketplace", name="Claude Code plugins")
        await fd.source(s, "skills-empty", connector="claude_marketplace", name="Agent Skills")
        await fd.source(s, "news", name="Some news feed")  # not a radar source

        def add(src, kind, name, *, days_ago, tags=(), initial=False, status="active", **kw):  # type: ignore[no-untyped-def]
            seen = NOW - timedelta(days=days_ago)
            row = AISkill(source_id=src.id, kind=kind, name=name, title=kw.pop("title", name),
                          listing_url=f"https://listing.test/{name}", first_seen_at=seen, last_seen_at=seen,
                          stack_tags=list(tags), initial=initial, status=status,
                          install=[{"label": "Install", "command": f"install {name}", "notes": []}], **kw)  # fmt: skip
            s.add(row)
            return row

        pg = add(reg, SkillKind.MCP_SERVER, "io.github.acme/postgres-mcp", days_ago=1, tags=("postgresql",),
                 description="Query PostgreSQL databases", publisher="io.github.acme",
                 facts={"packages": [{"registryType": "npm"}]})  # fmt: skip
        add(reg, SkillKind.MCP_SERVER, "com.example/weather", days_ago=2, description="Weather forecasts")
        add(reg, SkillKind.MCP_SERVER, "com.example/old", days_ago=30, tags=("docker",))
        add(reg, SkillKind.MCP_SERVER, "com.example/gone", days_ago=1, status="deleted", tags=("docker",))
        add(market, SkillKind.PLUGIN, "security-guidance", days_ago=3, tags=("security",), initial=True,
            category="security")  # fmt: skip
        add(market, SkillKind.PLUGIN, "brand-new", days_ago=0, tags=("docker", "github"))
        add(market, SkillKind.SKILL, "pdf", days_ago=3, initial=True, category="document-skills")
        await s.commit()
        return pg.id


async def _names(client, **params):  # type: ignore[no-untyped-def]
    r = await client.get("/api/v1/skills", params=params)
    assert r.status_code == 200, r.text
    return [i["name"] for i in r.json()["items"]]


async def test_list_filters_and_order(client, session_factory):
    await _seed(session_factory)
    r = await client.get("/api/v1/skills")
    body = r.json()
    names = [i["name"] for i in body["items"]]
    assert names[0] == "brand-new" and "com.example/gone" not in names and body["total"] == 6  # active only
    first = body["items"][0]
    assert first["source"] == {"slug": "plugins", "name": "Claude Code plugins"}
    assert first["install"] == [{"label": "Install", "command": "install brand-new", "notes": []}]
    assert "facts" not in first and first["is_new"] is True
    flags = {i["name"]: i["is_new"] for i in body["items"]}
    assert flags["security-guidance"] is False and flags["com.example/old"] is False  # baseline, too old

    assert await _names(client, kind="plugin") == ["brand-new", "security-guidance"]
    assert set(await _names(client, kind=["skill", "plugin"])) == {"brand-new", "security-guidance", "pdf"}
    assert set(await _names(client, source="mcp-reg")) == {
        "io.github.acme/postgres-mcp", "com.example/weather", "com.example/old"}  # fmt: skip
    assert set(await _names(client, stack=["docker", "postgresql"])) == {
        "brand-new", "com.example/old", "io.github.acme/postgres-mcp"}  # fmt: skip
    assert len(await _names(client, fits="true")) == 4
    assert await _names(client, q="postgresql") == ["io.github.acme/postgres-mcp"]  # description match
    assert await _names(client, q="ACME") == ["io.github.acme/postgres-mcp"]  # publisher, any case
    # New in 7 days: first seen recently and not part of a marketplace's first collection.
    assert await _names(client, days=7) == ["brand-new", "io.github.acme/postgres-mcp", "com.example/weather"]
    assert "com.example/gone" in await _names(client, include_inactive="true", page_size=100)
    assert await _names(client, sort="name", kind="plugin") == ["brand-new", "security-guidance"]

    assert (await client.get("/api/v1/skills", params={"stack": "cobol"})).status_code == 422
    assert (await client.get("/api/v1/skills", params={"kind": "agent"})).status_code == 422
    assert (await client.get("/api/v1/skills", params={"days": 0})).status_code == 422
    assert (await client.get("/api/v1/skills", params={"sort": "-description"})).status_code == 400
    assert (await client.get("/api/v1/skills", params={"bogus": 1})).status_code in (400, 422)


async def test_facets_and_detail(client, session_factory):
    pg = await _seed(session_factory)
    f = (await client.get("/api/v1/skills/facets")).json()
    assert {k["value"]: k["count"] for k in f["kinds"]} == {"mcp_server": 3, "plugin": 2, "skill": 1}
    assert (
        f["stack"][0] == {"value": "docker", "count": 2} and {"value": "postgresql", "count": 1} in f["stack"]
    )
    sources = {x["slug"]: x for x in f["sources"]}
    assert set(sources) == {"mcp-reg", "plugins", "skills-empty"}  # radar sources only, empty ones too
    assert sources["mcp-reg"]["entries"] == 3 and sources["skills-empty"]["entries"] == 0
    assert f["new_last_7_days"] == 3

    d = (await client.get(f"/api/v1/skills/{pg}")).json()
    assert d["facts"] == {"packages": [{"registryType": "npm"}]} and d["publisher"] == "io.github.acme"
    assert (
        d["kind"] == "mcp_server" and d["listing_url"] == "https://listing.test/io.github.acme/postgres-mcp"
    )
    missing = await client.get("/api/v1/skills/00000000-0000-0000-0000-000000000001")
    assert missing.status_code == 404
