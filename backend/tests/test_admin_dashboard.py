from tests.conftest import make_admin, register_and_login

SRC = {
    "slug": "k8s-blog",
    "name": "Kubernetes Blog",
    "source_type": "rss",
    "connector": "rss",
    "url": "https://kubernetes.io/feed.xml",
    "default_item_type": "devops",
    "is_official": True,
    "reliability": 0.95,
}


async def test_admin_requires_admin_role(client):
    assert (await client.get("/api/v1/admin/sources")).status_code == 401
    token = await register_and_login(client, "plain@example.com")
    r = await client.get("/api/v1/admin/sources", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


async def test_admin_source_crud(client, session_factory):
    await register_and_login(client, "admin@example.com")
    await make_admin(session_factory, "admin@example.com")
    r = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "Sup3r-Secret-pass!"}
    )
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await client.post("/api/v1/admin/sources", json=SRC, headers=h)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert (await client.post("/api/v1/admin/sources", json=SRC, headers=h)).status_code == 409
    bad = {**SRC, "slug": "x", "url": "not-a-url"}
    assert (await client.post("/api/v1/admin/sources", json=bad, headers=h)).status_code == 422

    r = await client.patch(
        f"/api/v1/admin/sources/{sid}", json={"enabled": False, "poll_interval_minutes": 30}, headers=h
    )
    assert r.json()["enabled"] is False and r.json()["poll_interval_minutes"] == 30
    assert (
        await client.patch(f"/api/v1/admin/sources/{sid}", json={"poll_interval_minutes": 1}, headers=h)
    ).status_code == 422
    r = await client.get("/api/v1/admin/sources", headers=h)
    assert len(r.json()) == 1
    assert (await client.delete(f"/api/v1/admin/sources/{sid}", headers=h)).status_code == 204


async def test_admin_cannot_delete_source_with_items(client, session_factory, seeded):
    await register_and_login(client, "admin2@example.com")
    await make_admin(session_factory, "admin2@example.com")
    r = await client.post(
        "/api/v1/auth/login", json={"email": "admin2@example.com", "password": "Sup3r-Secret-pass!"}
    )
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await client.delete(f"/api/v1/admin/sources/{seeded['source']}", headers=h)
    assert r.status_code == 409


async def test_dashboard_summary_counts_real_data(client, seeded):
    r = await client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    d = r.json()
    assert d["total_articles"] == 3
    assert d["articles_last_24h"] == 3
    assert d["active_incidents"] == 0
    assert len(d["activity_14d"]) == 14 and d["activity_14d"][-1]["count"] == 3
    assert [a["id"] for a in d["top_security"]] == [str(seeded["a3"])]


async def test_dashboard_empty_state(client):
    d = (await client.get("/api/v1/dashboard/summary")).json()
    assert d["total_articles"] == 0 and d["latest"] == []
