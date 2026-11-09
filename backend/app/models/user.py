import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BriefingFrequency, RoleName, Severity, enum_column


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[RoleName] = mapped_column(enum_column(RoleName, "role_name"), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship(lazy="joined")
    preference: Mapped["UserPreference | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    interests: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    followed_technologies: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, server_default="{}"
    )
    followed_repositories: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), default=list, server_default="{}"
    )
    followed_providers: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, server_default="{}"
    )
    min_notification_severity: Mapped[Severity] = mapped_column(
        enum_column(Severity, "severity"), default=Severity.HIGH, server_default=Severity.HIGH.value
    )
    briefing_frequency: Mapped[BriefingFrequency] = mapped_column(
        enum_column(BriefingFrequency, "briefing_frequency"),
        default=BriefingFrequency.DAILY,
        server_default=BriefingFrequency.DAILY.value,
    )
    briefing_hour: Mapped[int] = mapped_column(Integer, default=7, server_default="7")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    theme: Mapped[str] = mapped_column(String(16), default="dark", server_default="dark")
    # Alert rules and thresholds (see app/alerts). Empty = defaults.
    alert_settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")

    user: Mapped[User] = relationship(back_populates="preference")


class RefreshToken(Base, UUIDPrimaryKeyMixin):
    """Opaque refresh token (hash only). `family_id` groups a rotation chain for reuse detection."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    user_agent: Mapped[str | None] = mapped_column(Text)


class PasswordResetToken(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
