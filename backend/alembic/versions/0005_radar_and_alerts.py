"""radar and alerts

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-09 19:42:00.618085
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _seed_source()
    op.add_column(
        "security_vulnerabilities", sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "software_bugs",
        sa.Column(
            "resolution",
            sa.Enum(
                "fixed",
                "completed",
                "not_planned",
                "duplicate",
                "unknown",
                name="bug_resolution",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
    )
    op.add_column("software_bugs", sa.Column("fix_merged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("software_bugs", sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "user_preferences",
        sa.Column(
            "alert_settings", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM sources s WHERE s.slug = 'github-advisories' "
        "AND NOT EXISTS (SELECT 1 FROM articles a WHERE a.source_id = s.id)"
    )
    op.drop_column("user_preferences", "alert_settings")
    op.drop_column("software_bugs", "last_verified_at")
    op.drop_column("software_bugs", "fix_merged_at")
    op.drop_column("software_bugs", "resolution")
    op.drop_column("security_vulnerabilities", "last_verified_at")


def _seed_source() -> None:
    import json
    import uuid

    from app.ingestion.catalog import DEFAULT_SOURCES

    src = next(x for x in DEFAULT_SOURCES if x["slug"] == "github-advisories")
    op.get_bind().execute(
        sa.text(
            "INSERT INTO sources (id, slug, name, source_type, connector, url, homepage_url, default_item_type, "
            "is_official, reliability, enabled, poll_interval_minutes, config) VALUES (:id, :slug, :name, "
            ":source_type, :connector, :url, :homepage_url, :default_item_type, :is_official, :reliability, "
            ":enabled, :poll_interval_minutes, CAST(:config AS JSONB)) ON CONFLICT (slug) DO NOTHING"
        ),
        {
            **{k: v for k, v in src.items() if k != "live_check"},
            "id": uuid.uuid4(),
            "config": json.dumps(src["config"]),
        },
    )
