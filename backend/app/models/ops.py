"""User-facing and operational entities: briefings, bookmarks, notifications, jobs, AI analyses."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AnalysisKind, JobStatus, NotificationKind, Severity, enum_column


class DailyBriefing(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "daily_briefings"
    __table_args__ = (UniqueConstraint("user_id", "briefing_date", name="uq_daily_briefings_user_date"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(  # NULL = global briefing
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    briefing_date: Mapped[date] = mapped_column(Date)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executive_summary: Mapped[str | None] = mapped_column(Text)
    sections: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    cited_article_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    llm_provider: Mapped[str | None] = mapped_column(String(32))
    llm_model: Mapped[str | None] = mapped_column(String(100))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Bookmark(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_bookmarks_user_article"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArticleRead(Base):
    """Per-user read/unread state."""

    __tablename__ = "article_reads"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Notification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        # Idempotency: the same event never produces two notifications for one user.
        UniqueConstraint("user_id", "dedup_key", name="uq_notifications_user_dedup"),
        Index("ix_notifications_user_unread", "user_id", "read_at"),
        Index("ix_notifications_user_kind_created", "user_id", "kind", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[NotificationKind] = mapped_column(enum_column(NotificationKind, "notification_kind"))
    severity: Mapped[Severity] = mapped_column(enum_column(Severity, "severity"))
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(Text)
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )
    link: Mapped[str | None] = mapped_column(String(2048))
    dedup_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # deleted by the user


class CollectionJob(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "collection_jobs"
    __table_args__ = (
        Index("ix_collection_jobs_source_started", "source_id", "started_at"),
        Index("ix_collection_jobs_status", "status"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE")
    )
    status: Mapped[JobStatus] = mapped_column(enum_column(JobStatus, "job_status"))
    trigger: Mapped[str] = mapped_column(String(32), default="schedule")  # schedule | manual | retry
    celery_task_id: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_fetched: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    items_created: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    items_updated: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    items_skipped: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    error: Mapped[str | None] = mapped_column(Text)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")


class AIAnalysis(Base, UUIDPrimaryKeyMixin):
    """Versioned AI output for an article. Always labelled as AI-generated in the UI."""

    __tablename__ = "ai_analyses"
    __table_args__ = (
        UniqueConstraint("article_id", "kind", "prompt_version", name="uq_ai_analyses_article_kind_version"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[AnalysisKind] = mapped_column(enum_column(AnalysisKind, "analysis_kind"))
    prompt_version: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))
    output: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    valid: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AIUsage(Base, UUIDPrimaryKeyMixin):
    """One LLM/embedding call: who/what/how much. Feeds cost tracking and the daily token budget."""

    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_created", "created_at"),)

    purpose: Mapped[str] = mapped_column(String(32))  # analysis | embedding | rag | briefing
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_usd: Mapped[float | None] = mapped_column(Float)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    error: Mapped[str | None] = mapped_column(Text)
    article_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LearningLesson(Base, UUIDPrimaryKeyMixin):
    """A short AI-generated technical lesson built from one collected item, for one user and day."""

    __tablename__ = "learning_lessons"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "lesson_date", "article_id", name="uq_learning_lessons_user_date_article"
        ),
        Index("ix_learning_lessons_user_date", "user_id", "lesson_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE")
    )
    lesson_date: Mapped[date] = mapped_column(Date)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    prompt_version: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WeeklyReport(Base, UUIDPrimaryKeyMixin):
    """One user's weekly intelligence report: the week's briefings merged (rendered to PDF on download)."""

    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_weekly_reports_user_week"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    week_start: Mapped[date] = mapped_column(Date)  # Monday, in the user's timezone
    week_end: Mapped[date] = mapped_column(Date)  # Sunday
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    briefing_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
