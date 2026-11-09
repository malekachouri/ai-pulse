import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.models import PasswordResetToken, RefreshToken, User, UserPreference
from app.models.enums import RoleName
from app.repositories.users import TokenRepository, UserRepository
from app.services.email import EmailSender

log = get_logger(__name__)

# Used to keep login timing similar whether or not the account exists.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings, email: EmailSender) -> None:
        self.session = session
        self.settings = settings
        self.email = email
        self.users = UserRepository(session)
        self.tokens = TokenRepository(session)

    async def register(
        self, email: str, password: str, full_name: str | None, role: RoleName = RoleName.USER
    ) -> User:
        if await self.users.get_by_email(email):
            raise ConflictError("An account with this email already exists")
        role_obj = await self.users.get_role(role)
        user = User(
            email=email.lower(),
            full_name=full_name,
            password_hash=hash_password(password),
            role_id=role_obj.id,
            is_active=True,
        )
        user.preference = UserPreference()
        return await self.users.add(user)

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        if user is None:
            verify_password(password, _DUMMY_HASH)
            raise AuthenticationError("Invalid email or password")
        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is disabled")
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.last_login_at = _now()
        return user

    async def issue_tokens(
        self, user: User, family_id: uuid.UUID | None = None, user_agent: str | None = None
    ) -> tuple[IssuedTokens, RefreshToken]:
        access, ttl = create_access_token(self.settings, user.id, user.role.name.value)
        raw = generate_opaque_token()
        now = _now()
        record = await self.tokens.add_refresh(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                family_id=family_id or uuid.uuid4(),
                issued_at=now,
                expires_at=now + timedelta(days=self.settings.refresh_token_ttl_days),
                user_agent=(user_agent or "")[:500] or None,
            )
        )
        return IssuedTokens(access, ttl, raw, record.expires_at), record

    async def login(self, email: str, password: str, user_agent: str | None = None) -> IssuedTokens:
        user = await self.authenticate(email, password)
        issued, _ = await self.issue_tokens(user, user_agent=user_agent)
        return issued

    async def refresh(self, raw_token: str | None, user_agent: str | None = None) -> IssuedTokens:
        """Rotate a refresh token. Re-use of an already-rotated token revokes the whole family."""
        if not raw_token:
            raise AuthenticationError("Missing refresh token")
        now = _now()
        record = await self.tokens.get_refresh_by_hash(hash_token(raw_token), for_update=True)
        if record is None:
            raise AuthenticationError("Invalid refresh token")
        if record.revoked_at is not None:
            log.warning(
                "refresh_token_reuse_detected", user_id=str(record.user_id), family=str(record.family_id)
            )
            await self.tokens.revoke_family(record.family_id, now)
            await self.session.commit()  # persist revocation even though we raise
            raise AuthenticationError("Refresh token reuse detected; please sign in again")
        if record.expires_at <= now:
            raise AuthenticationError("Refresh token expired")
        user = await self.users.get(record.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Account is disabled")
        issued, new_record = await self.issue_tokens(user, family_id=record.family_id, user_agent=user_agent)
        record.revoked_at = now
        record.replaced_by_id = new_record.id
        return issued

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        record = await self.tokens.get_refresh_by_hash(hash_token(raw_token))
        if record is not None:
            await self.tokens.revoke_family(record.family_id, _now())

    async def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            raise AuthenticationError("Current password is incorrect")
        user.password_hash = hash_password(new)
        await self.tokens.revoke_all_for_user(user.id, _now())

    async def request_password_reset(self, email: str) -> str | None:
        """Create a reset token; returns it (dev exposure only). Callers respond identically either way."""
        user = await self.users.get_by_email(email)
        if user is None or not user.is_active:
            return None
        now = _now()
        await self.tokens.invalidate_resets_for_user(user.id, now)
        raw = generate_opaque_token()
        await self.tokens.add_reset(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                created_at=now,
                expires_at=now + timedelta(minutes=self.settings.password_reset_ttl_minutes),
            )
        )
        await self.email.send(
            user.email,
            "Reset your AI Pulse password",
            f"Use this token to reset your password within {self.settings.password_reset_ttl_minutes} "
            f"minutes: {raw}",
        )
        return raw

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        now = _now()
        record = await self.tokens.get_reset_by_hash(hash_token(raw_token))
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise AuthenticationError("Invalid or expired reset token")
        user = await self.users.get(record.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Invalid or expired reset token")
        user.password_hash = hash_password(new_password)
        record.used_at = now
        await self.tokens.revoke_all_for_user(user.id, now)
