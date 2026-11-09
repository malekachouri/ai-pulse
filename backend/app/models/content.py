"""Sources, categories and the canonical `articles` table.

Every collected record (news post, release, CVE, issue, incident...) becomes one row in
`articles` holding the *original* content and provenance. Type-specific structured data
lives in dedicated tables that reference the article. AI output is stored separately in
`ai_analyses` so confirmed facts are never mixed with generated analysis.
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ItemType, Severity, SourceType, VerificationStatus, enum_column

EMBEDDING_DIM = 768  # OpenAI text-embedding-3-* with dimensions=768, or nomic-embed-text on Ollama

article_categories = Table(
    "article_categories",
    Base.metadata,
    Column("article_id", UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))


class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("reliability >= 0 AND reliability <= 1", name="reliability_range"),
        CheckConstraint("poll_interval_minutes >= 5", name="poll_interval_min"),
    )

    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[SourceType] = mapped_column(enum_column(SourceType, "source_type"))
    connector: Mapped[str] = mapped_column(String(100))  # connector implementation key
    url: Mapped[str] = mapped_column(String(2048))
    homepage_url: Mapped[str | None] = mapped_column(String(2048))
    default_item_type: Mapped[ItemType] = mapped_column(enum_column(ItemType, "item_type"))
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reliability: Mapped[float] = mapped_column(Float, default=0.5, server_default="0.5")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Article(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_articles_source_external"),
        CheckConstraint(
            "importance_score IS NULL OR (importance_score BETWEEN 0 AND 100)", name="importance"
        ),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_item_type_published", "item_type", "published_at"),
        Index("ix_articles_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_articles_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(512))  # stable id from the source (guid, CVE id...)
    item_type: Mapped[ItemType] = mapped_column(enum_column(ItemType, "item_type"))
    title: Mapped[str] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)  # original text, never AI-modified
    url: Mapped[str] = mapped_column(String(2048))  # original source URL (mandatory)
    author: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str | None] = mapped_column(String(8))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # from source
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # when we fetched it
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        enum_column(VerificationStatus, "verification_status")
    )
    severity: Mapped[Severity | None] = mapped_column(enum_column(Severity, "severity"))
    severity_basis: Mapped[str | None] = mapped_column(String(200))  # e.g. "NVD CVSS v3.1 base score 9.8"
    importance_score: Mapped[float | None] = mapped_column(Float)  # AI Pulse score, NOT CVSS
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"), index=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(description, '')), 'B') || "
            "setweight(to_tsvector('english', left(coalesce(content, ''), 100000)), 'C')",
            persisted=True,
        ),
    )

    source: Mapped[Source] = relationship(lazy="joined")
    categories: Mapped[list[Category]] = relationship(secondary=article_categories, lazy="selectin")
