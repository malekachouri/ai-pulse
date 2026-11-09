"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-09 09:29:23.151299
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "ai_models",
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("family", sa.String(length=100), nullable=True),
        sa.Column("modality", postgresql.ARRAY(sa.String(length=32)), server_default="{}", nullable=False),
        sa.Column("is_open_weights", sa.Boolean(), nullable=True),
        sa.Column("homepage_url", sa.String(length=2048), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_models")),
        sa.UniqueConstraint("provider", "name", name="uq_ai_models_provider_name"),
    )
    op.create_index(op.f("ix_ai_models_provider"), "ai_models", ["provider"], unique=False)
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("slug", name=op.f("uq_categories_slug")),
    )
    op.create_table(
        "github_repositories",
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("github_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("html_url", sa.String(length=2048), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("topics", postgresql.ARRAY(sa.String(length=64)), server_default="{}", nullable=False),
        sa.Column("stars", sa.Integer(), server_default="0", nullable=False),
        sa.Column("forks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("open_issues", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stars_delta_7d", sa.Integer(), nullable=True),
        sa.Column("latest_release", sa.String(length=100), nullable=True),
        sa.Column("latest_release_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "star_history", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("tracked", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_github_repositories")),
        sa.UniqueConstraint("full_name", name=op.f("uq_github_repositories_full_name")),
        sa.UniqueConstraint("github_id", name=op.f("uq_github_repositories_github_id")),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "name",
            sa.Enum(
                "admin",
                "analyst",
                "user",
                name="role_name",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_table(
        "sources",
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "rss",
                "api",
                "github",
                "status_page",
                "scrape",
                name="source_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("connector", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("homepage_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "default_item_type",
            sa.Enum(
                "news",
                "model_release",
                "tool",
                "research",
                "github_repo",
                "github_issue",
                "bug",
                "vulnerability",
                "incident",
                "devops",
                name="item_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("is_official", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("reliability", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("poll_interval_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("checkpoint", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("poll_interval_minutes >= 5", name=op.f("ck_sources_poll_interval_min")),
        sa.CheckConstraint(
            "reliability >= 0 AND reliability <= 1", name=op.f("ck_sources_reliability_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
        sa.UniqueConstraint("slug", name=op.f("uq_sources_slug")),
    )
    op.create_table(
        "articles",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=False),
        sa.Column(
            "item_type",
            sa.Enum(
                "news",
                "model_release",
                "tool",
                "research",
                "github_repo",
                "github_issue",
                "bug",
                "vulnerability",
                "incident",
                "devops",
                name="item_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("author", sa.String(length=300), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "verification_status",
            sa.Enum(
                "official",
                "verified",
                "unverified",
                "disputed",
                name="verification_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                "info",
                "unknown",
                name="severity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("severity_basis", sa.String(length=200), nullable=True),
        sa.Column("importance_score", sa.Float(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=64)), server_default="{}", nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("duplicate_of_id", sa.UUID(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(title, '')), 'A') || setweight(to_tsvector('english', coalesce(description, '')), 'B') || setweight(to_tsvector('english', left(coalesce(content, ''), 100000)), 'C')",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "importance_score IS NULL OR (importance_score BETWEEN 0 AND 100)",
            name=op.f("ck_articles_importance"),
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["articles.id"],
            name=op.f("fk_articles_duplicate_of_id_articles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name=op.f("fk_articles_source_id_sources"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_articles")),
        sa.UniqueConstraint("source_id", "external_id", name="uq_articles_source_external"),
    )
    op.create_index(op.f("ix_articles_content_hash"), "articles", ["content_hash"], unique=False)
    op.create_index(op.f("ix_articles_duplicate_of_id"), "articles", ["duplicate_of_id"], unique=False)
    op.create_index(
        "ix_articles_embedding_hnsw",
        "articles",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_articles_item_type_published", "articles", ["item_type", "published_at"], unique=False
    )
    op.create_index("ix_articles_published_at", "articles", ["published_at"], unique=False)
    op.create_index(
        "ix_articles_search_vector", "articles", ["search_vector"], unique=False, postgresql_using="gin"
    )
    op.create_index(op.f("ix_articles_source_id"), "articles", ["source_id"], unique=False)
    op.create_table(
        "collection_jobs",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "succeeded",
                "failed",
                "partial",
                name="job_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_fetched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_collection_jobs_source_id_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_jobs")),
    )
    op.create_index(
        "ix_collection_jobs_source_started", "collection_jobs", ["source_id", "started_at"], unique=False
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_users_role_id_roles"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"], unique=False)
    op.create_table(
        "ai_analyses",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "summary",
                "classification",
                "impact",
                "importance",
                "entities",
                name="analysis_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("valid", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_ai_analyses_article_id_articles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_analyses")),
        sa.UniqueConstraint(
            "article_id", "kind", "prompt_version", name="uq_ai_analyses_article_kind_version"
        ),
    )
    op.create_index(op.f("ix_ai_analyses_article_id"), "ai_analyses", ["article_id"], unique=False)
    op.create_table(
        "ai_model_releases",
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.String(length=100), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_ai_model_releases_article_id_articles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["ai_models.id"],
            name=op.f("fk_ai_model_releases_model_id_ai_models"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_model_releases")),
    )
    op.create_index(op.f("ix_ai_model_releases_model_id"), "ai_model_releases", ["model_id"], unique=False)
    op.create_table(
        "ai_tools",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("homepage_url", sa.String(length=2048), nullable=True),
        sa.Column("repository_id", sa.UUID(), nullable=True),
        sa.Column("latest_version", sa.String(length=100), nullable=True),
        sa.Column("license", sa.String(length=100), nullable=True),
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles.id"], name=op.f("fk_ai_tools_article_id_articles"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["github_repositories.id"],
            name=op.f("fk_ai_tools_repository_id_github_repositories"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_tools")),
        sa.UniqueConstraint("name", name=op.f("uq_ai_tools_name")),
    )
    op.create_table(
        "article_categories",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_article_categories_article_id_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_article_categories_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("article_id", "category_id", name=op.f("pk_article_categories")),
    )
    op.create_table(
        "article_reads",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_article_reads_article_id_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_article_reads_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "article_id", name=op.f("pk_article_reads")),
    )
    op.create_table(
        "audit_logs",
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_audit_logs_actor_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_table(
        "bookmarks",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles.id"], name=op.f("fk_bookmarks_article_id_articles"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_bookmarks_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookmarks")),
        sa.UniqueConstraint("user_id", "article_id", name="uq_bookmarks_user_article"),
    )
    op.create_index(op.f("ix_bookmarks_user_id"), "bookmarks", ["user_id"], unique=False)
    op.create_table(
        "daily_briefings",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("briefing_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column(
            "cited_article_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("llm_provider", sa.String(length=32), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_daily_briefings_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_briefings")),
        sa.UniqueConstraint("user_id", "briefing_date", name="uq_daily_briefings_user_date"),
    )
    op.create_index(op.f("ix_daily_briefings_user_id"), "daily_briefings", ["user_id"], unique=False)
    op.create_table(
        "github_issues",
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("html_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "open", "closed", name="issue_state", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column("labels", postgresql.ARRAY(sa.String(length=100)), server_default="{}", nullable=False),
        sa.Column("is_pull_request", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("comments", sa.Integer(), server_default="0", nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_github_issues_article_id_articles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["github_repositories.id"],
            name=op.f("fk_github_issues_repository_id_github_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_github_issues")),
        sa.UniqueConstraint("article_id", name=op.f("uq_github_issues_article_id")),
        sa.UniqueConstraint("repository_id", "number", name="uq_github_issues_repo_number"),
    )
    op.create_index(op.f("ix_github_issues_repository_id"), "github_issues", ["repository_id"], unique=False)
    op.create_table(
        "incidents",
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column(
            "affected_services", postgresql.ARRAY(sa.String(length=200)), server_default="{}", nullable=False
        ),
        sa.Column("regions", postgresql.ARRAY(sa.String(length=64)), server_default="{}", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "investigating",
                "identified",
                "monitoring",
                "resolved",
                "unknown",
                name="incident_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("impact", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_page_url", sa.String(length=2048), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updates", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_incidents_article_id_articles"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
        sa.UniqueConstraint("article_id", name=op.f("uq_incidents_article_id")),
        sa.UniqueConstraint("provider", "external_id", name="uq_incidents_provider_external"),
    )
    op.create_index(op.f("ix_incidents_provider"), "incidents", ["provider"], unique=False)
    op.create_table(
        "notifications",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "critical_alert",
                "model_release",
                "vulnerability",
                "bug",
                "incident",
                "briefing",
                "system",
                name="notification_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                "info",
                "unknown",
                name="severity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("link", sa.String(length=2048), nullable=True),
        sa.Column("dedup_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_notifications_article_id_articles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("user_id", "dedup_key", name="uq_notifications_user_dedup"),
    )
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "read_at"], unique=False)
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_password_reset_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.create_table(
        "research_papers",
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("arxiv_id", sa.String(length=32), nullable=True),
        sa.Column("doi", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("authors", postgresql.ARRAY(sa.String(length=300)), server_default="{}", nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("primary_category", sa.String(length=32), nullable=True),
        sa.Column("pdf_url", sa.String(length=2048), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_research_papers_article_id_articles"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_papers")),
        sa.UniqueConstraint("article_id", name=op.f("uq_research_papers_article_id")),
        sa.UniqueConstraint("arxiv_id", name=op.f("uq_research_papers_arxiv_id")),
    )
    op.create_table(
        "security_vulnerabilities",
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("cve_id", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("cvss_version", sa.String(length=8), nullable=True),
        sa.Column("cvss_vector", sa.String(length=200), nullable=True),
        sa.Column(
            "severity",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                "info",
                "unknown",
                name="severity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("cwe_ids", postgresql.ARRAY(sa.String(length=32)), server_default="{}", nullable=False),
        sa.Column(
            "affected_products", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("known_exploited", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("kev_date_added", sa.Date(), nullable=True),
        sa.Column("kev_due_date", sa.Date(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("patch_available", sa.Boolean(), nullable=True),
        sa.Column("references", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "cvss_score IS NULL OR (cvss_score BETWEEN 0 AND 10)",
            name=op.f("ck_security_vulnerabilities_cvss_range"),
        ),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_security_vulnerabilities_article_id_articles"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_vulnerabilities")),
        sa.UniqueConstraint("article_id", name=op.f("uq_security_vulnerabilities_article_id")),
        sa.UniqueConstraint("cve_id", name=op.f("uq_security_vulnerabilities_cve_id")),
    )
    op.create_index(
        "ix_security_vulnerabilities_published", "security_vulnerabilities", ["published_at"], unique=False
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("interests", postgresql.ARRAY(sa.String(length=64)), server_default="{}", nullable=False),
        sa.Column(
            "followed_technologies",
            postgresql.ARRAY(sa.String(length=100)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "followed_repositories",
            postgresql.ARRAY(sa.String(length=200)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "followed_providers", postgresql.ARRAY(sa.String(length=100)), server_default="{}", nullable=False
        ),
        sa.Column(
            "min_notification_severity",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                "info",
                "unknown",
                name="severity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="high",
            nullable=False,
        ),
        sa.Column(
            "briefing_frequency",
            sa.Enum(
                "daily",
                "weekdays",
                "weekly",
                "off",
                name="briefing_frequency",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="daily",
            nullable=False,
        ),
        sa.Column("briefing_hour", sa.Integer(), server_default="7", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("theme", sa.String(length=16), server_default="dark", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_preferences_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferences")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_preferences_user_id")),
    )
    op.create_table(
        "software_bugs",
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("github_issue_id", sa.UUID(), nullable=True),
        sa.Column("project", sa.String(length=200), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "bug",
                "regression",
                "performance",
                "compatibility",
                "security",
                "other",
                name="bug_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                "info",
                "unknown",
                name="severity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("severity_basis", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "open", "closed", name="issue_state", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column(
            "affected_versions", postgresql.ARRAY(sa.String(length=64)), server_default="{}", nullable=False
        ),
        sa.Column("fixed_in_version", sa.String(length=64), nullable=True),
        sa.Column("fix_url", sa.String(length=2048), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_software_bugs_article_id_articles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["github_issue_id"],
            ["github_issues.id"],
            name=op.f("fk_software_bugs_github_issue_id_github_issues"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_software_bugs")),
        sa.UniqueConstraint("article_id", name=op.f("uq_software_bugs_article_id")),
        sa.UniqueConstraint("github_issue_id", name=op.f("uq_software_bugs_github_issue_id")),
    )
    op.create_index(op.f("ix_software_bugs_project"), "software_bugs", ["project"], unique=False)
    _seed()


def downgrade() -> None:
    op.drop_index(op.f("ix_software_bugs_project"), table_name="software_bugs")
    op.drop_table("software_bugs")
    op.drop_table("user_preferences")
    op.drop_index("ix_security_vulnerabilities_published", table_name="security_vulnerabilities")
    op.drop_table("security_vulnerabilities")
    op.drop_table("research_papers")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_incidents_provider"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_index(op.f("ix_github_issues_repository_id"), table_name="github_issues")
    op.drop_table("github_issues")
    op.drop_index(op.f("ix_daily_briefings_user_id"), table_name="daily_briefings")
    op.drop_table("daily_briefings")
    op.drop_index(op.f("ix_bookmarks_user_id"), table_name="bookmarks")
    op.drop_table("bookmarks")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("article_reads")
    op.drop_table("article_categories")
    op.drop_table("ai_tools")
    op.drop_index(op.f("ix_ai_model_releases_model_id"), table_name="ai_model_releases")
    op.drop_table("ai_model_releases")
    op.drop_index(op.f("ix_ai_analyses_article_id"), table_name="ai_analyses")
    op.drop_table("ai_analyses")
    op.drop_index(op.f("ix_users_role_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index("ix_collection_jobs_source_started", table_name="collection_jobs")
    op.drop_table("collection_jobs")
    op.drop_index(op.f("ix_articles_source_id"), table_name="articles")
    op.drop_index("ix_articles_search_vector", table_name="articles", postgresql_using="gin")
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_index("ix_articles_item_type_published", table_name="articles")
    op.drop_index(
        "ix_articles_embedding_hnsw",
        table_name="articles",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_index(op.f("ix_articles_duplicate_of_id"), table_name="articles")
    op.drop_index(op.f("ix_articles_content_hash"), table_name="articles")
    op.drop_table("articles")
    op.drop_table("sources")
    op.drop_table("roles")
    op.drop_table("github_repositories")
    op.drop_table("categories")
    op.drop_index(op.f("ix_ai_models_provider"), table_name="ai_models")
    op.drop_table("ai_models")


ROLES = [
    ("admin", "Full administrative access"),
    ("analyst", "Can trigger ingestion and manage content"),
    ("user", "Standard reader"),
]

CATEGORIES = [
    ("ai-models", "AI Models"),
    ("ai-research", "AI Research"),
    ("ai-tools", "AI Tools"),
    ("rag", "RAG"),
    ("llmops", "LLMOps"),
    ("mlops", "MLOps"),
    ("ai-agents", "AI Agents"),
    ("software-engineering", "Software Engineering"),
    ("bugs", "Bugs"),
    ("infrastructure-failures", "Infrastructure Failures"),
    ("cybersecurity", "Cybersecurity"),
    ("devops", "DevOps"),
    ("cloud", "Cloud"),
    ("kubernetes", "Kubernetes"),
    ("docker", "Docker"),
]


def _seed() -> None:
    roles = sa.table("roles", sa.column("name", sa.String), sa.column("description", sa.String))
    op.bulk_insert(roles, [{"name": n, "description": d} for n, d in ROLES])
    cats = sa.table("categories", sa.column("slug", sa.String), sa.column("name", sa.String))
    op.bulk_insert(cats, [{"slug": s, "name": n} for s, n in CATEGORIES])
