import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.repositories.articles import ArticleRepository
from app.schemas.article import ArticleDetail, ArticleFilters, ArticleOut
from app.schemas.common import Page, PageParams


class ArticleService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ArticleRepository(session)

    async def search(self, filters: ArticleFilters, page: PageParams, user: User | None) -> Page[ArticleOut]:
        rows, total = await self.repo.search(filters, page.offset, page.page_size)
        items = [ArticleOut.model_validate(r) for r in rows]
        if user and items:
            bookmarked, read = await self.repo.user_flags(user.id, [i.id for i in items])
            for item in items:
                item.is_bookmarked = item.id in bookmarked
                item.is_read = item.id in read
        return Page.build(items, total, page)

    async def get(self, article_id: uuid.UUID, user: User | None) -> ArticleDetail:
        article = await self.repo.get(article_id)
        if article is None:
            raise NotFoundError("Article not found")
        detail = ArticleDetail.model_validate(article)
        if user:
            bookmarked, read = await self.repo.user_flags(user.id, [article.id])
            detail.is_bookmarked = article.id in bookmarked
            detail.is_read = article.id in read
        return detail

    async def set_read(self, article_id: uuid.UUID, user: User, read: bool) -> None:
        if await self.repo.get(article_id) is None:
            raise NotFoundError("Article not found")
        if read:
            await self.repo.mark_read(user.id, article_id, datetime.now(UTC))
        else:
            await self.repo.mark_unread(user.id, article_id)
