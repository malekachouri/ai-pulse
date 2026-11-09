import pytest

from tests.conftest import PASSWORD, register_and_login

AUTH = "/api/v1/auth"


async def test_register_validates_password_strength(client):
    r = await client.post(f"{AUTH}/register", json={"email": "a@example.com", "password": "short"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    r = await client.post(
        f"{AUTH}/register", json={"email": "a@example.com", "password": "alllowercaseletters"}
    )
    assert r.status_code == 422


async def test_register_duplicate_email_case_insensitive(client):
    await register_and_login(client, "dup@example.com")
    r = await client.post(f"{AUTH}/register", json={"email": "DUP@example.com", "password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


async def test_register_never_returns_password_hash(client):
    r = await client.post(f"{AUTH}/register", json={"email": "h@example.com", "password": PASSWORD})
    assert r.status_code == 201
    body = r.json()
    assert "password" not in str(body).lower()
    assert body["role"] == "user"


async def test_login_wrong_password_and_unknown_user(client):
    await register_and_login(client, "x@example.com")
    r = await client.post(f"{AUTH}/login", json={"email": "x@example.com", "password": "wrong-Password-1"})
    assert r.status_code == 401
    r = await client.post(f"{AUTH}/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid email or password"


async def test_login_sets_httponly_refresh_cookie_and_me_works(client):
    token = await register_and_login(client, "me@example.com")
    set_cookie = client.cookies.get("aipulse_refresh")
    assert set_cookie
    r = await client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["email"] == "me@example.com"


async def test_login_cookie_flags(client):
    await client.post(f"{AUTH}/register", json={"email": "c@example.com", "password": PASSWORD})
    r = await client.post(f"{AUTH}/login", json={"email": "c@example.com", "password": PASSWORD})
    header = r.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=strict" in header and "path=/api/v1/auth" in header


async def test_me_requires_valid_token(client):
    assert (await client.get(f"{AUTH}/me")).status_code == 401
    r = await client.get(f"{AUTH}/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


async def test_refresh_rotation_and_reuse_detection(client):
    await register_and_login(client, "r@example.com")
    first = client.cookies.get("aipulse_refresh")

    r = await client.post(f"{AUTH}/refresh")
    assert r.status_code == 200
    second = client.cookies.get("aipulse_refresh")
    assert second and second != first

    # Replaying the old (rotated) token is detected and kills the whole family.
    client.cookies.set("aipulse_refresh", first, path="/api/v1/auth")
    r = await client.post(f"{AUTH}/refresh")
    assert r.status_code == 401
    assert "reuse" in r.json()["error"]["message"].lower()

    client.cookies.set("aipulse_refresh", second, path="/api/v1/auth")
    r = await client.post(f"{AUTH}/refresh")
    assert r.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await register_and_login(client, "l@example.com")
    token = client.cookies.get("aipulse_refresh")
    assert (await client.post(f"{AUTH}/logout")).status_code == 200
    client.cookies.set("aipulse_refresh", token, path="/api/v1/auth")
    assert (await client.post(f"{AUTH}/refresh")).status_code == 401


async def test_refresh_without_cookie(client):
    r = await client.post(f"{AUTH}/refresh")
    assert r.status_code == 401


async def test_update_profile_and_change_password(client):
    token = await register_and_login(client, "p@example.com")
    h = {"Authorization": f"Bearer {token}"}
    r = await client.patch(f"{AUTH}/me", json={"full_name": "Ada"}, headers=h)
    assert r.json()["full_name"] == "Ada"
    r = await client.post(
        f"{AUTH}/change-password",
        headers=h,
        json={"current_password": "Wrong-pass-123", "new_password": "N3w-Secret-pass!"},
    )
    assert r.status_code == 401
    r = await client.post(
        f"{AUTH}/change-password",
        headers=h,
        json={"current_password": PASSWORD, "new_password": "N3w-Secret-pass!"},
    )
    assert r.status_code == 200
    r = await client.post(f"{AUTH}/login", json={"email": "p@example.com", "password": "N3w-Secret-pass!"})
    assert r.status_code == 200


@pytest.mark.parametrize("known", [True, False])
async def test_password_reset_request_is_uniform(client, email_sender, known):
    if known:
        await register_and_login(client, "reset@example.com")
    r = await client.post(f"{AUTH}/password-reset/request", json={"email": "reset@example.com"})
    assert r.status_code == 200
    assert r.json()["reset_token"] is None  # never exposed unless explicitly enabled for dev
    assert len(email_sender.sent) == (1 if known else 0)


async def test_password_reset_flow(client, email_sender):
    await register_and_login(client, "flow@example.com")
    old_refresh = client.cookies.get("aipulse_refresh")
    await client.post(f"{AUTH}/password-reset/request", json={"email": "flow@example.com"})
    raw = email_sender.sent[-1][2].rsplit(" ", 1)[-1]

    r = await client.post(
        f"{AUTH}/password-reset/confirm", json={"token": raw, "new_password": "Brand-new-Pass9"}
    )
    assert r.status_code == 200
    # token is single-use
    r = await client.post(
        f"{AUTH}/password-reset/confirm", json={"token": raw, "new_password": "Another-Pass99"}
    )
    assert r.status_code == 401
    # existing sessions revoked
    client.cookies.set("aipulse_refresh", old_refresh, path="/api/v1/auth")
    assert (await client.post(f"{AUTH}/refresh")).status_code == 401
    r = await client.post(f"{AUTH}/login", json={"email": "flow@example.com", "password": "Brand-new-Pass9"})
    assert r.status_code == 200
