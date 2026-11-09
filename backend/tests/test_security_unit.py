import pytest

from app.core.config import Settings
from app.core.errors import AuthenticationError
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def _s(**kw):
    return Settings(jwt_secret="unit-test-secret-key-0123456789abcdef", **kw)


def test_password_hash_roundtrip():
    h = hash_password("Correct-horse-9")
    assert h.startswith("$argon2id$")
    assert verify_password("Correct-horse-9", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "not-a-hash")


def test_access_token_roundtrip_and_tamper():
    import uuid

    s = _s()
    uid = uuid.uuid4()
    tok, ttl = create_access_token(s, uid, "user")
    assert ttl == 15 * 60
    assert decode_access_token(s, tok)["sub"] == str(uid)
    with pytest.raises(AuthenticationError):
        decode_access_token(_s(jwt_issuer="other"), tok)
    with pytest.raises(AuthenticationError):
        decode_access_token(Settings(jwt_secret="a-different-secret-0123456789abcdefgh"), tok)


def test_expired_token():
    import uuid

    s = _s(access_token_ttl_minutes=-1)
    tok, _ = create_access_token(s, uuid.uuid4(), "user")
    with pytest.raises(AuthenticationError, match="expired"):
        decode_access_token(s, tok)


def test_production_rejects_weak_secret():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="production")
    with pytest.raises(ValueError, match="EXPOSE_RESET_TOKEN"):
        Settings(environment="production", jwt_secret="x" * 40, expose_reset_token=True)
