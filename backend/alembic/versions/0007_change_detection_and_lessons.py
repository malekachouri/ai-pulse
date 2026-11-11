"""release change detection (analysis kind) and learning lessons

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-11 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = ("summary", "classification", "impact", "importance", "entities")
KINDS_AFTER = (*KINDS_BEFORE, "changes")


def _kind_check(kinds: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ai_analyses_analysis_kind"), "ai_analyses", type_="check")
    op.create_check_constraint(op.f("ck_ai_analyses_analysis_kind"), "ai_analyses", _kind_check(KINDS_AFTER))
    op.create_table(
        "learning_lessons",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("lesson_date", sa.Date(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name="fk_learning_lessons_article_id_articles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_learning_lessons_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_learning_lessons"),
        sa.UniqueConstraint(
            "user_id", "lesson_date", "article_id", name="uq_learning_lessons_user_date_article"
        ),
    )
    op.create_index("ix_learning_lessons_user_date", "learning_lessons", ["user_id", "lesson_date"])


def downgrade() -> None:
    op.drop_index("ix_learning_lessons_user_date", table_name="learning_lessons")
    op.drop_table("learning_lessons")
    op.execute("DELETE FROM ai_analyses WHERE kind = 'changes'")
    op.drop_constraint(op.f("ck_ai_analyses_analysis_kind"), "ai_analyses", type_="check")
    op.create_check_constraint(op.f("ck_ai_analyses_analysis_kind"), "ai_analyses", _kind_check(KINDS_BEFORE))
