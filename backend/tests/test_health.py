async def test_live(client):
    r = await client.get("/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_ready_checks_db_and_pgvector(client):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["checks"] == {"database": "ok", "pgvector": "ok"}


async def test_metrics_and_security_headers(client):
    await client.get("/health/live")
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "aipulse_http_requests_total" in r.text
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_unknown_route_uses_error_envelope(client):
    r = await client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
