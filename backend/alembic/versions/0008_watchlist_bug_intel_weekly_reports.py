"""watchlist notifications, bug intelligence analyses and weekly reports

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-11 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = ("summary", "classification", "impact", "importance", "entities", "changes")
KINDS_AFTER = (*KINDS_BEFORE, "bug_intel")
NOTIF_BEFORE = ("critical_alert", "model_release", "vulnerability", "bug", "incident", "briefing", "system")
NOTIF_AFTER = (*NOTIF_BEFORE, "watchlist")


def _check(kinds: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def _set(table: str, name: str, kinds: tuple[str, ...]) -> None:
    op.drop_constraint(op.f(name), table, type_="check")
    op.create_check_constraint(op.f(name), table, _check(kinds))


def upgrade() -> None:
    _set("ai_analyses", "ck_ai_analyses_analysis_kind", KINDS_AFTER)
    _set("notifications", "ck_notifications_notification_kind", NOTIF_AFTER)
    op.create_table(
        "weekly_reports",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "briefing_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_weekly_reports_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_weekly_reports"),
        sa.UniqueConstraint("user_id", "week_start", name="uq_weekly_reports_user_week"),
    )
    op.create_index(op.f("ix_weekly_reports_user_id"), "weekly_reports", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_weekly_reports_user_id"), table_name="weekly_reports")
    op.drop_table("weekly_reports")
    op.execute("DELETE FROM notifications WHERE kind = 'watchlist'")
    _set("notifications", "ck_notifications_notification_kind", NOTIF_BEFORE)
    op.execute("DELETE FROM ai_analyses WHERE kind = 'bug_intel'")
    _set("ai_analyses", "ck_ai_analyses_analysis_kind", KINDS_BEFORE)
