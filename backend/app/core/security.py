"""Password hashing (Argon2id), JWT access tokens and opaque refresh/reset tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import Settings
from app.core.errors import AuthenticationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError, InvalidHashError:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(settings: Settings, user_id: uuid.UUID, role: str) -> tuple[str, int]:
    now = datetime.now(UTC)
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)
    return token, int(ttl.total_seconds())


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Access token expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid access token") from exc
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    return payload


def generate_opaque_token() -> str:
    """High-entropy URL-safe token (refresh / password reset). Only its hash is stored."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
