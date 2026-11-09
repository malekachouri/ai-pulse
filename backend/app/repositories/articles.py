import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, and_, desc, exists, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleRead, Bookmark, Category, Source, article_categories
from app.schemas.article import ArticleFilters, SortOrder


class ArticleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    def _filtered(self, f: ArticleFilters) -> tuple[Select, object | None]:
        stmt = select(Article)
        ts_query = None
        if f.q:
            ts_query = func.websearch_to_tsquery("english", f.q)
            stmt = stmt.where(Article.search_vector.op("@@")(ts_query))
        if f.item_type:
            stmt = stmt.where(Article.item_type.in_(f.item_type))
        if f.severity:
            stmt = stmt.where(Article.severity.in_(f.severity))
        if f.verification:
            stmt = stmt.where(Article.verification_status.in_(f.verification))
        if f.min_importance is not None:
            stmt = stmt.where(Article.importance_score >= f.min_importance)
        if f.date_from:
            stmt = stmt.where(func.coalesce(Article.published_at, Article.collected_at) >= f.date_from)
        if f.date_to:
            stmt = stmt.where(func.coalesce(Article.published_at, Article.collected_at) <= f.date_to)
        if not f.include_duplicates:
            stmt = stmt.where(Article.duplicate_of_id.is_(None))
        if f.source:
            stmt = stmt.where(Article.source_id.in_(select(Source.id).where(Source.slug.in_(f.source))))
        if f.category:
            stmt = stmt.where(
                exists().where(
                    and_(
                        article_categories.c.article_id == Article.id,
                        article_categories.c.category_id.in_(
                            select(Category.id).where(Category.slug.in_(f.category))
                        ),
                    )
                )
            )
        return stmt, ts_query

    async def search(self, f: ArticleFilters, offset: int, limit: int) -> tuple[Sequence[Article], int]:
        stmt, ts_query = self._filtered(f)
        total = await self.s.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        when = func.coalesce(Article.published_at, Article.collected_at)
        if f.sort == SortOrder.RELEVANCE and ts_query is not None:
            stmt = stmt.order_by(desc(func.ts_rank_cd(Article.search_vector, ts_query)), desc(when))
        elif f.sort == SortOrder.IMPORTANCE:
            stmt = stmt.order_by(nulls_last(desc(Article.importance_score)), desc(when))
        else:
            stmt = stmt.order_by(desc(when), desc(Article.id))
        rows = (await self.s.scalars(stmt.offset(offset).limit(limit))).unique().all()
        return rows, total

    async def get(self, article_id: uuid.UUID) -> Article | None:
        return await self.s.get(Article, article_id)

    async def user_flags(
        self, user_id: uuid.UUID, article_ids: Sequence[uuid.UUID]
    ) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        if not article_ids:
            return set(), set()
        bookmarked = set(
            await self.s.scalars(
                select(Bookmark.article_id).where(
                    Bookmark.user_id == user_id, Bookmark.article_id.in_(article_ids)
                )
            )
        )
        read = set(
            await self.s.scalars(
                select(ArticleRead.article_id).where(
                    ArticleRead.user_id == user_id, ArticleRead.article_id.in_(article_ids)
                )
            )
        )
        return bookmarked, read

    async def mark_read(self, user_id: uuid.UUID, article_id: uuid.UUID, now: datetime) -> None:
        from sqlalchemy.dialects.postgresql import insert

        await self.s.execute(
            insert(ArticleRead)
            .values(user_id=user_id, article_id=article_id, read_at=now)
            .on_conflict_do_nothing()
        )

    async def mark_unread(self, user_id: uuid.UUID, article_id: uuid.UUID) -> None:
        from sqlalchemy import delete

        await self.s.execute(
            delete(ArticleRead).where(ArticleRead.user_id == user_id, ArticleRead.article_id == article_id)
        )
