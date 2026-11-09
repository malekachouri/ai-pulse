"""Shared query helpers: whitelisted sorting, pagination and safe text matching."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError


class SortSpec:
    """Parses `sort=field` / `sort=-field` against an explicit whitelist of sortable columns.

    Descending sorts put NULLs last; a stable tiebreaker column is always appended.
    """

    def __init__(
        self, fields: Mapping[str, ColumnElement[Any]], default: str, tiebreaker: ColumnElement[Any]
    ):
        self.fields = fields
        self.default = default
        self.tiebreaker = tiebreaker

    def allowed(self) -> list[str]:
        return [f"{p}{k}" for k in self.fields for p in ("", "-")]

    def order_by(self, sort: str | None) -> list[Any]:
        raw = (sort or self.default).strip()
        desc = raw.startswith("-")
        key = raw.removeprefix("-")
        col = self.fields.get(key)
        if col is None:
            raise AppError(f"Invalid sort '{raw}'", details={"allowed": self.allowed()})
        return [nulls_last(col.desc()) if desc else col.asc(), self.tiebreaker.desc()]


async def paginate(
    session: AsyncSession, stmt: Select[Any], order_by: Sequence[Any], offset: int, limit: int
) -> tuple[Sequence[Any], int]:
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = (await session.scalars(stmt.order_by(*order_by).offset(offset).limit(limit))).unique().all()
    return rows, total


def contains_pattern(text: str) -> str:
    """ILIKE pattern for a literal substring (escapes %, _ and the escape char)."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
