"""Skills radar queries."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import AISkill, Source
from app.repositories.base import SortSpec, contains_pattern, paginate
from app.schemas.common import Page
from app.schemas.skills import FacetCount, SkillDetail, SkillFacets, SkillFilters, SkillOut, SourceStatus

ACTIVE = "active"
NEW_DAYS = 7
SKILL_SORT = SortSpec(
    {"first_seen_at": AISkill.first_seen_at, "published_at": AISkill.published_at, "name": AISkill.name,
     "updated_at": AISkill.source_updated_at},
    default="-first_seen_at", tiebreaker=AISkill.id,
)  # fmt: skip
SKILL_CONNECTORS = ("mcp_registry", "claude_marketplace")


class SkillsService:
    def __init__(self, session: AsyncSession, now: datetime | None = None) -> None:
        self.s = session
        self.now = now or datetime.now(UTC)

    def _filtered(self, f: SkillFilters) -> Select[tuple[AISkill]]:
        stmt = select(AISkill)
        if not f.include_inactive:
            stmt = stmt.where(AISkill.status == ACTIVE)
        if f.kind:
            stmt = stmt.where(AISkill.kind.in_(f.kind))
        if f.source:
            stmt = stmt.where(AISkill.source_id.in_(select(Source.id).where(Source.slug.in_(f.source))))
        if f.stack:
            stmt = stmt.where(AISkill.stack_tags.overlap(f.stack))
        if f.fits:
            stmt = stmt.where(func.cardinality(AISkill.stack_tags) > 0)
        if f.days:
            since = self.now - timedelta(days=f.days)
            stmt = stmt.where(AISkill.first_seen_at >= since, AISkill.initial.is_(False))
        if f.q:
            pattern = contains_pattern(f.q)
            cols = (AISkill.name, AISkill.title, AISkill.description, AISkill.publisher)
            stmt = stmt.where(or_(*(c.ilike(pattern, escape="\\") for c in cols)))
        return stmt

    async def list(self, f: SkillFilters) -> Page[SkillOut]:
        rows, total = await paginate(
            self.s, self._filtered(f), SKILL_SORT.order_by(f.sort), f.paging.offset, f.page_size
        )
        return Page.build([self._out(SkillOut, r) for r in rows], total, f.paging)

    async def get(self, skill_id: uuid.UUID) -> SkillDetail:
        row = await self.s.get(AISkill, skill_id)
        if row is None:
            raise NotFoundError("Skill not found")
        return self._out(SkillDetail, row)

    def _out[T: SkillOut](self, schema: type[T], row: AISkill) -> T:
        out = schema.model_validate(row)
        out.is_new = not row.initial and row.first_seen_at >= self.now - timedelta(days=NEW_DAYS)
        if row.explanation:
            out.explained_at = datetime.fromisoformat(row.explanation["generated_at"])
        return out

    async def facets(self) -> SkillFacets:
        active = AISkill.status == ACTIVE
        kinds = await self.s.execute(
            select(AISkill.kind, func.count()).where(active).group_by(AISkill.kind).order_by(AISkill.kind)
        )
        tag = func.unnest(AISkill.stack_tags).label("tag")
        tags_q = select(tag).where(active).subquery()
        stack = await self.s.execute(
            select(tags_q.c.tag, func.count())
            .group_by(tags_q.c.tag)
            .order_by(func.count().desc(), tags_q.c.tag)
        )
        counts = (
            select(AISkill.source_id, func.count().label("n"))
            .where(active)
            .group_by(AISkill.source_id)
            .subquery()
        )
        sources = await self.s.execute(
            select(Source, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.source_id == Source.id)
            .where(Source.connector.in_(SKILL_CONNECTORS))
            .order_by(Source.name)
        )
        new = await self.s.scalar(
            select(func.count()).where(
                and_(
                    active,
                    AISkill.initial.is_(False),
                    AISkill.first_seen_at >= self.now - timedelta(days=NEW_DAYS),
                )
            )
        )
        return SkillFacets(
            kinds=[FacetCount(value=k.value, count=n) for k, n in kinds],
            stack=[FacetCount(value=t, count=n) for t, n in stack],
            sources=[
                SourceStatus(
                    slug=src.slug,
                    name=src.name,
                    entries=n,
                    last_success_at=src.last_success_at,
                    last_error=src.last_error if src.consecutive_failures else None,
                )
                for src, n in sources.unique()
            ],  # fmt: skip
            new_last_7_days=new or 0,
        )
