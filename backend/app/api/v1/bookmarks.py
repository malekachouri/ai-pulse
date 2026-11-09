import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.models import Article, Bookmark
from app.schemas.common import ErrorResponse, Page, PageParams
from app.schemas.user_data import BookmarkOut, BookmarkUpsert
from app.services.articles import ArticleService

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"], responses={401: {"model": ErrorResponse}})


@router.get("", response_model=Page[BookmarkOut])
async def list_bookmarks(
    session: SessionDep,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[BookmarkOut]:
    params = PageParams(page=page, page_size=page_size)
    total = await session.scalar(select(func.count(Bookmark.id)).where(Bookmark.user_id == user.id)) or 0
    rows = (
        await session.execute(
            select(Bookmark, Article)
            .join(Article, Article.id == Bookmark.article_id)
            .where(Bookmark.user_id == user.id)
            .order_by(Bookmark.created_at.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
    ).all()
    articles = await ArticleService(session).to_out([a for _, a in rows], user)
    items = [
        BookmarkOut(id=b.id, note=b.note, created_at=b.created_at, article=art)
        for (b, _), art in zip(rows, articles, strict=True)
    ]
    return Page.build(items, total, params)


@router.put(
    "/{article_id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"model": ErrorResponse}}
)
async def add_bookmark(
    article_id: uuid.UUID, session: SessionDep, user: CurrentUser, body: BookmarkUpsert | None = None
) -> None:
    if await session.get(Article, article_id) is None:
        raise NotFoundError("Article not found")
    note = body.note if body else None
    stmt = insert(Bookmark).values(
        id=uuid.uuid4(), user_id=user.id, article_id=article_id, note=note, created_at=datetime.now(UTC)
    )
    await session.execute(
        stmt.on_conflict_do_update(constraint="uq_bookmarks_user_article", set_={"note": stmt.excluded.note})
        if body
        else stmt.on_conflict_do_nothing()
    )


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bookmark(article_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    await session.execute(
        delete(Bookmark).where(Bookmark.user_id == user.id, Bookmark.article_id == article_id)
    )
