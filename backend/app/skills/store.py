"""Saving radar entries: one row per (source, kind, name), updated in place when the listing changes."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AISkill
from app.models.enums import SkillKind
from app.skills.stack import stack_tags

# Fields compared to decide whether a listing changed (dates of the run itself are not content).
_CONTENT = ("title", "description", "version", "publisher", "category", "status", "listing_url",
            "homepage_url", "repository_url", "install", "facts", "stack_tags", "published_at",
            "source_updated_at")  # fmt: skip


@dataclass
class SkillRecord:
    kind: SkillKind
    name: str
    listing_url: str
    title: str | None = None
    description: str | None = None
    version: str | None = None
    publisher: str | None = None
    category: str | None = None
    status: str = "active"
    homepage_url: str | None = None
    repository_url: str | None = None
    install: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    published_at: datetime | None = None
    source_updated_at: datetime | None = None

    def values(self) -> dict[str, Any]:
        v = {k: getattr(self, k) for k in _CONTENT if k != "stack_tags"}
        v["title"] = (self.title or "")[:300] or None
        v["description"] = (self.description or "")[:5000] or None
        # Not the namespace: "io.github.<user>/x" says where it is published, not what it does.
        local_name = self.name.rsplit("/", 1)[-1]
        v["stack_tags"] = stack_tags(local_name, self.title, self.description, self.category)
        return v


@dataclass
class StoreStats:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


async def upsert(
    session: AsyncSession, source_id: uuid.UUID, records: list[SkillRecord], now: datetime, *, initial: bool
) -> StoreStats:
    """Insert new entries (first seen now) and update changed ones. `initial` marks a source's first
    collection, whose entries were already listed before AI Pulse watched them."""
    stats = StoreStats()
    unique = {(r.kind, r.name): r for r in records}  # the last occurrence wins
    keys = list(unique)
    for start in range(0, len(keys), 500):
        chunk = keys[start : start + 500]
        rows = await session.scalars(
            select(AISkill).where(AISkill.source_id == source_id, AISkill.name.in_([n for _, n in chunk]))
        )
        existing = {(r.kind, r.name): r for r in rows}
        for key in chunk:
            values = unique[key].values()
            row = existing.get(key)
            if row is None:
                session.add(AISkill(source_id=source_id, kind=key[0], name=key[1], first_seen_at=now,
                                    last_seen_at=now, initial=initial, **values))  # fmt: skip
                stats.created += 1
                continue
            row.last_seen_at = now
            changed = {k: v for k, v in values.items() if getattr(row, k) != v}
            if changed:
                for k, v in changed.items():
                    setattr(row, k, v)
                stats.updated += 1
            else:
                stats.unchanged += 1
    await session.flush()
    return stats


async def mark_removed(session: AsyncSession, source_id: uuid.UUID, keep: dict[SkillKind, set[str]]) -> int:
    """Entries of a full listing (a marketplace) that left it: status "removed", kept for history."""
    removed = 0
    for kind, names in keep.items():
        stmt = update(AISkill).where(
            AISkill.source_id == source_id, AISkill.kind == kind, AISkill.status != "removed"
        )
        if names:
            stmt = stmt.where(AISkill.name.not_in(names))
        result = await session.execute(stmt.values(status="removed"))
        removed += int(result.rowcount or 0)  # type: ignore[attr-defined]
    return removed
