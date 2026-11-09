"""ingestion sources

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-09 13:53:06.131285
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("canonical_key", sa.String(length=200), nullable=True))
    op.create_index(op.f("ix_articles_canonical_key"), "articles", ["canonical_key"], unique=False)
    _seed_sources()


def downgrade() -> None:
    # Seeded sources are kept only if nothing references them (collected articles keep their provenance).
    op.execute(
        "DELETE FROM sources s WHERE s.slug = ANY(:slugs) AND NOT EXISTS (SELECT 1 FROM articles a WHERE a.source_id = s.id)".replace(
            ":slugs", "ARRAY[" + ",".join(f"'{x['slug']}'" for x in _catalog()) + "]"
        )
    )
    op.drop_index(op.f("ix_articles_canonical_key"), table_name="articles")
    op.drop_column("articles", "canonical_key")


def _catalog() -> list[dict]:
    from app.ingestion.catalog import DEFAULT_SOURCES

    return DEFAULT_SOURCES


def _seed_sources() -> None:
    import json
    import uuid

    bind = op.get_bind()
    for src in _catalog():
        bind.execute(
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
