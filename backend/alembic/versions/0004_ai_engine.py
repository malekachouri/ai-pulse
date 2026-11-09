"""ai engine

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-09 14:25:10.207267
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX IF NOT EXISTS ix_articles_title_trgm ON articles USING gin (title gin_trgm_ops)")
    op.create_table(
        "ai_usage",
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("ok", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage")),
    )
    op.create_index("ix_ai_usage_created", "ai_usage", ["created_at"], unique=False)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_title_trgm")
    op.drop_index("ix_ai_usage_created", table_name="ai_usage")
    op.drop_table("ai_usage")
