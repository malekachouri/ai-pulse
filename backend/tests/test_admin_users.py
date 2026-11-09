from datetime import UTC, datetime, timedelta

from app.models import CollectionJob
from app.models.enums import JobStatus
from tests.conftest import PASSWORD, make_admin, register_and_login


async def _admin(client, session_factory, email="root@example.com") -> dict[str, str]:
    await register_and_login(client, email)
    await make_admin(session_factory, email)
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_admin_endpoints_require_admin(client, session_factory):
    token = await register_and_login(client, "plain@example.com")
    h = {"Authorization": f"Bearer {token}"}
    for path in ("/users", "/roles", "/jobs", "/audit-logs"):
        assert (await client.get(f"/api/v1/admin{path}")).status_code == 401
        assert (await client.get(f"/api/v1/admin{path}", headers=h)).status_code == 403


async def test_list_filter_and_roles(client, session_factory):
    h = await _admin(client, session_factory)
    await register_and_login(client, "alice@example.com")
    await register_and_login(client, "bob@example.com")
    r = await client.get("/api/v1/admin/users", params={"sort": "email"}, headers=h)
    assert [u["email"] for u in r.json()["items"]] == [
        "alice@example.com",
        "bob@example.com",
        "root@example.com",
    ]
    r = await client.get("/api/v1/admin/users", params={"role": "admin"}, headers=h)
    assert [u["email"] for u in r.json()["items"]] == ["root@example.com"]
    r = await client.get("/api/v1/admin/users", params={"q": "ALI"}, headers=h)
    assert r.json()["total"] == 1
    roles = {x["name"]: x["user_count"] for x in (await client.get("/api/v1/admin/roles", headers=h)).json()}
    assert roles == {"admin": 1, "analyst": 0, "user": 2}


async def test_update_user_role_and_deactivate(client, session_factory):
    h = await _admin(client, session_factory)
    await register_and_login(client, "victim@example.com")
    victim_refresh = client.cookies.get("aipulse_refresh")
    users = (await client.get("/api/v1/admin/users", params={"q": "victim"}, headers=h)).json()["items"]
    uid = users[0]["id"]

    r = await client.patch(f"/api/v1/admin/users/{uid}", json={"role": "analyst"}, headers=h)
    assert r.status_code == 200 and r.json()["role"] == "analyst"
    r = await client.patch(f"/api/v1/admin/users/{uid}", json={"is_active": False}, headers=h)
    assert r.json()["is_active"] is False

    # deactivated user is signed out everywhere and cannot log in
    client.cookies.set("aipulse_refresh", victim_refresh, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    r = await client.post("/api/v1/auth/login", json={"email": "victim@example.com", "password": PASSWORD})
    assert r.status_code == 401

    logs = (await client.get("/api/v1/admin/audit-logs", params={"action": "user.update"}, headers=h)).json()
    assert logs["total"] == 2
    assert logs["items"][0]["actor_email"] == "root@example.com"
    assert logs["items"][0]["details"] == {"is_active": {"from": True, "to": False}}
    assert (
        await client.patch(f"/api/v1/admin/users/{uid}", json={"role": "god"}, headers=h)
    ).status_code == 422


async def test_admin_cannot_lock_themselves_out(client, session_factory):
    h = await _admin(client, session_factory)
    me = (await client.get("/api/v1/auth/me", headers=h)).json()["id"]
    r = await client.patch(f"/api/v1/admin/users/{me}", json={"role": "user"}, headers=h)
    assert r.status_code == 403
    r = await client.patch(f"/api/v1/admin/users/{me}", json={"is_active": False}, headers=h)
    assert r.status_code == 403
    # a no-op update on yourself is fine
    assert (
        await client.patch(f"/api/v1/admin/users/{me}", json={"role": "admin"}, headers=h)
    ).status_code == 200


async def test_last_admin_cannot_be_removed(client, session_factory):
    h1 = await _admin(client, session_factory, "a1@example.com")
    h2 = await _admin(client, session_factory, "a2@example.com")
    a2 = (await client.get("/api/v1/auth/me", headers=h2)).json()["id"]
    a1 = (await client.get("/api/v1/auth/me", headers=h1)).json()["id"]
    assert (
        await client.patch(f"/api/v1/admin/users/{a2}", json={"role": "user"}, headers=h1)
    ).status_code == 200
    # a1 is now the only admin; promote a2 back and try to demote a1 via a2? a2 is no longer admin:
    assert (
        await client.patch(f"/api/v1/admin/users/{a1}", json={"role": "user"}, headers=h2)
    ).status_code == 403


async def test_jobs_visible_to_analysts(client, session_factory, seeded):
    await register_and_login(client, "analyst@example.com")
    from sqlalchemy import text

    async with session_factory() as s:
        await s.execute(
            text("UPDATE users SET role_id=(SELECT id FROM roles WHERE name='analyst') WHERE email=:e"),
            {"e": "analyst@example.com"},
        )
        now = datetime.now(UTC)
        s.add_all([
            CollectionJob(source_id=seeded["source"], status=JobStatus.SUCCEEDED, started_at=now - timedelta(minutes=10),
                          finished_at=now - timedelta(minutes=9), items_fetched=10, items_created=4),
            CollectionJob(source_id=seeded["source"], status=JobStatus.FAILED, started_at=now,
                          error="HTTP 503 from source"),
        ])  # fmt: skip
        await s.commit()
    r = await client.post("/api/v1/auth/login", json={"email": "analyst@example.com", "password": PASSWORD})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    jobs = (await client.get("/api/v1/admin/jobs", headers=h)).json()
    assert [j["status"] for j in jobs["items"]] == ["failed", "succeeded"]
    assert jobs["items"][1]["duration_seconds"] == 60.0 and jobs["items"][0]["duration_seconds"] is None
    r = await client.get("/api/v1/admin/jobs", params={"status": "failed", "source": "test-feed"}, headers=h)
    assert r.json()["items"][0]["error"] == "HTTP 503 from source"
    # analysts still can't manage users
    assert (await client.get("/api/v1/admin/users", headers=h)).status_code == 403
