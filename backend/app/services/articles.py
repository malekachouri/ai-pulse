import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import AIAnalysis, Article, User
from app.models.enums import AnalysisKind
from app.repositories.articles import ArticleRepository
from app.schemas.article import AISummary, ArticleDetail, ArticleFilters, ArticleOut
from app.schemas.common import Page, PageParams


class ArticleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ArticleRepository(session)

    async def _summaries(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, AISummary]:
        if not ids:
            return {}
        rows = await self.session.scalars(
            select(AIAnalysis)
            .where(
                AIAnalysis.article_id.in_(ids),
                AIAnalysis.kind == AnalysisKind.SUMMARY,
                AIAnalysis.valid.is_(True),
            )
            .order_by(AIAnalysis.article_id, AIAnalysis.created_at.desc())
            .distinct(AIAnalysis.article_id)
        )
        out: dict[uuid.UUID, AISummary] = {}
        for a in rows:
            short = (a.output or {}).get("short_summary")
            if isinstance(short, str) and short.strip():
                out[a.article_id] = AISummary(
                    short=short.strip(), provider=a.provider, model=a.model, generated_at=a.created_at
                )
        return out

    async def to_out[T: ArticleOut](
        self, rows: Sequence[Article], user: User | None, schema: type[T] = ArticleOut
    ) -> list[T]:
        """Serialize articles and attach per-user flags and the latest valid AI summary."""
        items = [schema.model_validate(r) for r in rows]
        ids = [i.id for i in items]
        summaries = await self._summaries(ids)
        bookmarked, read = (await self.repo.user_flags(user.id, ids)) if user else (set(), set())
        for item in items:
            item.ai_summary = summaries.get(item.id)
            item.is_bookmarked = item.id in bookmarked
            item.is_read = item.id in read
        return items

    async def search(self, filters: ArticleFilters, page: PageParams, user: User | None) -> Page[ArticleOut]:
        rows, total = await self.repo.search(filters, page.offset, page.page_size)
        return Page.build(await self.to_out(rows, user), total, page)

    async def get(self, article_id: uuid.UUID, user: User | None) -> ArticleDetail:
        article = await self.repo.get(article_id)
        if article is None:
            raise NotFoundError("Article not found")
        return (await self.to_out([article], user, ArticleDetail))[0]

    async def set_read(self, article_id: uuid.UUID, user: User, read: bool) -> None:
        if await self.repo.get(article_id) is None:
            raise NotFoundError("Article not found")
        if read:
            await self.repo.mark_read(user.id, article_id, datetime.now(UTC))
        else:
            await self.repo.mark_unread(user.id, article_id)
