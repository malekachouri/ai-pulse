import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.models import Notification
from app.models.enums import NotificationKind
from app.schemas.common import ErrorResponse, Page, PageParams
from app.schemas.user_data import NotificationFilters, NotificationOut, UnreadCount

router = APIRouter(prefix="/notifications", tags=["notifications"], responses={401: {"model": ErrorResponse}})


@router.get("", response_model=Page[NotificationOut])
async def list_notifications(
    session: SessionDep, user: CurrentUser, f: Annotated[NotificationFilters, Query()]
) -> Page[NotificationOut]:
    params = PageParams(page=f.page, page_size=f.page_size)
    stmt = select(Notification).where(Notification.user_id == user.id, Notification.dismissed_at.is_(None))
    if f.unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    if f.kind:
        stmt = stmt.where(Notification.kind.in_(f.kind))
    if f.severity:
        stmt = stmt.where(Notification.severity.in_(f.severity))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(Notification.created_at.desc(), Notification.id)
        .offset(params.offset)
        .limit(params.page_size)
    )
    return Page.build([NotificationOut.model_validate(n) for n in rows], total, params)


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(session: SessionDep, user: CurrentUser) -> UnreadCount:
    rows = (
        await session.execute(
            select(Notification.kind, func.count(Notification.id))
            .where(
                Notification.user_id == user.id,
                Notification.read_at.is_(None),
                Notification.dismissed_at.is_(None),
            )
            .group_by(Notification.kind)
        )
    ).all()
    by_kind = {k.value: n for k, n in rows}
    return UnreadCount(unread=sum(by_kind.values()), by_kind=by_kind)


async def _own(session: SessionDep, user: CurrentUser, notification_id: uuid.UUID) -> Notification:
    n = await session.get(Notification, notification_id)
    # 404 for other users' notifications too, so their existence is never revealed
    if n is None or n.user_id != user.id or n.dismissed_at is not None:
        raise NotFoundError("Notification not found")
    return n


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def mark_read(notification_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    n = await _own(session, user, notification_id)
    if n.read_at is None:
        n.read_at = datetime.now(UTC)


@router.post(
    "/{notification_id}/unread",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def mark_unread(notification_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    (await _own(session, user, notification_id)).read_at = None


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    description="Deleting does not re-enable the alert: the same event is never notified twice.",
)
async def delete_notification(notification_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    # Soft delete: the row (and its dedup key) stays so the same event never comes back.
    n = await _own(session, user, notification_id)
    now = datetime.now(UTC)
    n.read_at = n.read_at or now
    n.dismissed_at = now


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    session: SessionDep,
    user: CurrentUser,
    kind: Annotated[list[NotificationKind] | None, Query(description="Only these kinds")] = None,
) -> None:
    stmt = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if kind:
        stmt = stmt.where(Notification.kind.in_(kind))
    await session.execute(stmt.values(read_at=datetime.now(UTC)))
