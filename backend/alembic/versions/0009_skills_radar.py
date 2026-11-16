"""skills radar: MCP servers, Claude Code plugins and Agent Skills from official listings

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-15 22:37:10.506679
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES = ("mcp-registry", "claude-plugins-official", "anthropic-agent-skills")


def upgrade() -> None:
    op.create_table(
        "ai_skills",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "mcp_server",
                "plugin",
                "skill",
                name="skill_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=100), nullable=True),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("listing_url", sa.String(length=2048), nullable=False),
        sa.Column("homepage_url", sa.String(length=2048), nullable=True),
        sa.Column("repository_url", sa.String(length=2048), nullable=True),
        sa.Column("install", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("stack_tags", postgresql.ARRAY(sa.String(length=32)), server_default="{}", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initial", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name=op.f("fk_ai_skills_source_id_sources"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_skills")),
        sa.UniqueConstraint("source_id", "kind", "name", name="uq_ai_skills_source_kind_name"),
    )
    op.create_index(op.f("ix_ai_skills_category"), "ai_skills", ["category"], unique=False)
    op.create_index("ix_ai_skills_first_seen_at", "ai_skills", ["first_seen_at"], unique=False)
    op.create_index(op.f("ix_ai_skills_kind"), "ai_skills", ["kind"], unique=False)
    op.create_index(op.f("ix_ai_skills_source_id"), "ai_skills", ["source_id"], unique=False)
    op.create_index(
        "ix_ai_skills_stack_tags", "ai_skills", ["stack_tags"], unique=False, postgresql_using="gin"
    )

    _seed_sources()


def _seed_sources() -> None:
    """The radar's catalog sources, for databases created before them (a new database gets them in 0003)."""
    import json
    import uuid

    from app.ingestion.catalog import DEFAULT_SOURCES

    for src in (x for x in DEFAULT_SOURCES if x["slug"] in SOURCES):
        op.get_bind().execute(
            sa.text(
                "INSERT INTO sources (id, slug, name, source_type, connector, url, homepage_url, "
                "default_item_type, is_official, reliability, enabled, poll_interval_minutes, config) VALUES "
                "(:id, :slug, :name, :source_type, :connector, :url, :homepage_url, :default_item_type, "
                ":is_official, :reliability, :enabled, :poll_interval_minutes, CAST(:config AS JSONB)) "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {
                **{k: v for k, v in src.items() if k != "live_check"},
                "id": uuid.uuid4(),
                "config": json.dumps(src["config"]),
            },
        )


def downgrade() -> None:
    # Their connectors do not exist before this revision. Collection jobs go with them (ON DELETE CASCADE).
    op.get_bind().execute(sa.text("DELETE FROM sources WHERE slug = ANY(:slugs)"), {"slugs": list(SOURCES)})
    op.drop_index("ix_ai_skills_stack_tags", table_name="ai_skills", postgresql_using="gin")
    op.drop_index(op.f("ix_ai_skills_source_id"), table_name="ai_skills")
    op.drop_index(op.f("ix_ai_skills_kind"), table_name="ai_skills")
    op.drop_index("ix_ai_skills_first_seen_at", table_name="ai_skills")
    op.drop_index(op.f("ix_ai_skills_category"), table_name="ai_skills")
    op.drop_table("ai_skills")
