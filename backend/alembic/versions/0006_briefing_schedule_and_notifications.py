"""briefing schedule and notifications

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-09 20:24:10.799905
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_notifications_user_kind_created", "notifications", ["user_id", "kind", "created_at"], unique=False
    )
    op.add_column("notifications", sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "user_preferences", sa.Column("briefing_weekday", sa.Integer(), server_default="0", nullable=False)
    )
    op.create_check_constraint(
        "ck_user_preferences_briefing_hour", "user_preferences", "briefing_hour BETWEEN 0 AND 23"
    )
    op.create_check_constraint(
        "ck_user_preferences_briefing_weekday", "user_preferences", "briefing_weekday BETWEEN 0 AND 6"
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_preferences_briefing_weekday", "user_preferences", type_="check")
    op.drop_constraint("ck_user_preferences_briefing_hour", "user_preferences", type_="check")
    op.drop_column("user_preferences", "briefing_weekday")
    op.drop_index("ix_notifications_user_kind_created", table_name="notifications")
    op.drop_column("notifications", "dismissed_at")
