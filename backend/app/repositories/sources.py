import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def list(self, enabled: bool | None = None) -> Sequence[Source]:
        stmt = select(Source).order_by(Source.name)
        if enabled is not None:
            stmt = stmt.where(Source.enabled.is_(enabled))
        return (await self.s.scalars(stmt)).all()

    async def get(self, source_id: uuid.UUID) -> Source | None:
        return await self.s.get(Source, source_id)

    async def get_by_slug(self, slug: str) -> Source | None:
        return await self.s.scalar(select(Source).where(Source.slug == slug))

    async def add(self, source: Source) -> Source:
        self.s.add(source)
        await self.s.flush()
        return source

    async def delete(self, source: Source) -> None:
        await self.s.delete(source)
        await self.s.flush()
