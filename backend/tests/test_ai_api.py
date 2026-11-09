from app.ai.pipeline import AnalysisPipeline
from tests.ai_fakes import ScriptedChat, analysis_reply, providers
from tests.conftest import PASSWORD, make_admin, register_and_login
from tests.test_ai_pipeline import corpus  # noqa: F401 - fixture


def _set(client, p):
    client._transport.app.state.ai_providers = p  # type: ignore[attr-defined]


async def _prep(session_factory, p):
    async with session_factory() as s:
        await AnalysisPipeline(s, p).run(llm_limit=2)
        await s.commit()


async def test_capabilities_and_semantic_modes(client, session_factory, corpus):  # noqa: F811
    caps = (await client.get("/api/v1/search/capabilities")).json()
    assert caps["semantic"] is False and caps["ask_mode"] == "sources-only"
    r = await client.get("/api/v1/search", params={"q": "rag", "mode": "hybrid"})
    assert r.status_code == 501 and "EMBEDDING_PROVIDER" in r.json()["error"]["message"]

    p = providers(embed=True)
    await _prep(session_factory, p)
    _set(client, p)
    caps = (await client.get("/api/v1/search/capabilities")).json()
    assert caps["semantic"] and caps["embedded_items"] == caps["total_items"] == 7
    for mode in ("semantic", "hybrid"):
        r = await client.get(
            "/api/v1/search", params={"q": "retrieval augmented generation rag", "mode": mode}
        )
        body = r.json()
        assert r.status_code == 200 and body["mode"] == mode and body["items"]
        assert "RAG" in body["items"][0]["article"]["title"]
    r = await client.get(
        "/api/v1/search", params={"q": "rag", "mode": "semantic", "item_type": "vulnerability"}
    )
    assert all(
        i["article"]["item_type"] == "vulnerability" for i in r.json()["items"]
    )  # metadata filter applied


async def test_ask_endpoint(client, session_factory, corpus):  # noqa: F811
    await _prep(session_factory, providers())
    r = await client.post(
        "/api/v1/search/ask", json={"question": "Which Kubernetes vulnerabilities were recently disclosed?"}
    )
    body = r.json()
    assert r.status_code == 200 and body["answer"] is None and body["sources"] and not body["insufficient"]
    _set(
        client,
        providers(ScriptedChat(default={"answer": "Two CVEs were disclosed [1][2].", "confidence": "high"})),
    )
    body = (
        await client.post(
            "/api/v1/search/ask",
            json={"question": "Which Kubernetes vulnerabilities were recently disclosed?"},
        )
    ).json()
    assert body["answer"].startswith("Two CVEs") and len(body["citations"]) == 2 and body["ai_generated"]
    body = (
        await client.post(
            "/api/v1/search/ask", json={"question": "What happened with quantum teleportation of cats?"}
        )
    ).json()
    assert body["insufficient"] and body["answer"] is None
    assert (await client.post("/api/v1/search/ask", json={"question": "hi"})).status_code == 422


async def test_article_analysis_endpoint(client, session_factory, corpus):  # noqa: F811
    p = providers(ScriptedChat(default=analysis_reply()))
    await _prep(session_factory, p)
    _set(client, p)
    token = await register_and_login(client, "reader@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.put("/api/v1/preferences", json={"interests": ["kubernetes"]}, headers=h)
    r = await client.get(f"/api/v1/news/{corpus['k8s-cve2']}/analysis", headers=h)
    d = r.json()
    assert r.status_code == 200 and d["importance"]["label"].endswith("Not an official CVSS score.")
    assert (
        d["importance"]["personal_score"] > d["importance"]["score"] and d["importance"]["personal_reasons"]
    )
    assert d["language"] == "en" and any(e["type"] == "cve" for e in d["entities"])
    statuses = {d["summary_status"]["status"]}
    other = (await client.get(f"/api/v1/news/{corpus['old']}/analysis")).json()
    statuses.add(other["summary_status"]["status"])
    assert statuses <= {"ready", "pending"}
    news = (await client.get("/api/v1/news")).json()["items"]
    assert (
        sum(bool(i["ai_summary"]) for i in news) == 2
    )  # the 2 most important items (llm_limit=2)  # surfaced on cards, labelled as AI by the UI


async def test_generate_briefing_endpoint(client, session_factory, corpus):  # noqa: F811
    await _prep(session_factory, providers())
    assert (await client.post("/api/v1/briefings/generate")).status_code == 401
    token = await register_and_login(client, "brief@example.com")
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/v1/briefings/generate", headers=h)
    assert r.status_code == 200 and r.json()["sections"]["vulnerabilities"]
    again = await client.post("/api/v1/briefings/generate", headers=h)
    assert again.json()["id"] == r.json()["id"]  # within 10 minutes -> same briefing
    latest = (await client.get("/api/v1/briefings/latest", headers=h)).json()
    assert latest["id"] == r.json()["id"]


async def test_admin_ai_status_and_run(client, session_factory, corpus):  # noqa: F811
    from tests.test_ingestion_api import FakeQueue

    q = FakeQueue()
    q.enqueue = lambda task, kwargs: q.sent.append((task, str(kwargs))) or "task-ai"  # type: ignore[method-assign]
    client._transport.app.state.task_queue = q  # type: ignore[attr-defined]
    p = providers(ScriptedChat(default=analysis_reply()), embed=True)
    await _prep(session_factory, p)
    _set(client, p)
    await register_and_login(client, "ai-admin@example.com")
    await make_admin(session_factory, "ai-admin@example.com")
    r = await client.post("/api/v1/auth/login", json={"email": "ai-admin@example.com", "password": PASSWORD})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    st = (await client.get("/api/v1/admin/ai/status", headers=h)).json()
    assert st["llm_provider"] == "fake" and st["embedding_provider"] == "fake-embed"
    assert (
        st["items_with_rules_analysis"] == 7
        and st["items_with_ai_summary"] == 2
        and st["items_with_embedding"] == 7
    )
    assert st["tokens_today"] > 0 and st["cost_today_usd"] > 0
    assert "key" not in str(st).lower()  # never exposes credentials
    r = await client.post("/api/v1/admin/ai/run", headers=h)
    assert r.status_code == 202 and q.sent[-1][0] == "aipulse.ai_analyze"
