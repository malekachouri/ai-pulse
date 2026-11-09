import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request, status

from app.api.deps import AdminUser, SessionDep
from app.core.errors import ConflictError, NotFoundError
from app.models import AuditLog, Source
from app.repositories.sources import SourceRepository
from app.schemas.common import ErrorResponse
from app.schemas.source import SourceCreate, SourceOut, SourceUpdate

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


def _audit(
    request: Request, actor: AdminUser, action: str, target: Source, details: dict | None = None
) -> AuditLog:
    return AuditLog(
        actor_id=actor.id,
        action=action,
        target_type="source",
        target_id=str(target.id),
        details=details or {},
        ip_address=request.client.host if request.client else None,
        created_at=datetime.now(UTC),
    )


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(session: SessionDep, _: AdminUser, enabled: bool | None = None) -> list[SourceOut]:
    return [SourceOut.model_validate(s) for s in await SourceRepository(session).list(enabled)]


@router.post(
    "/sources",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_source(
    body: SourceCreate, request: Request, session: SessionDep, admin: AdminUser
) -> SourceOut:
    repo = SourceRepository(session)
    if await repo.get_by_slug(body.slug):
        raise ConflictError(f"Source '{body.slug}' already exists")
    data = body.model_dump(mode="json")
    source = await repo.add(Source(**data))
    session.add(_audit(request, admin, "source.create", source, {"slug": body.slug}))
    return SourceOut.model_validate(source)


@router.patch("/sources/{source_id}", response_model=SourceOut, responses={404: {"model": ErrorResponse}})
async def update_source(
    source_id: uuid.UUID, body: SourceUpdate, request: Request, session: SessionDep, admin: AdminUser
) -> SourceOut:
    source = await SourceRepository(session).get(source_id)
    if source is None:
        raise NotFoundError("Source not found")
    changes = body.model_dump(mode="json", exclude_unset=True)
    for key, value in changes.items():
        setattr(source, key, value)
    session.add(_audit(request, admin, "source.update", source, changes))
    await session.flush()
    await session.refresh(source)
    return SourceOut.model_validate(source)


@router.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def delete_source(
    source_id: uuid.UUID, request: Request, session: SessionDep, admin: AdminUser
) -> None:
    repo = SourceRepository(session)
    source = await repo.get(source_id)
    if source is None:
        raise NotFoundError("Source not found")
    from sqlalchemy import func, select

    from app.models import Article

    if await session.scalar(select(func.count(Article.id)).where(Article.source_id == source.id)):
        raise ConflictError("Source has collected items; disable it instead of deleting")
    session.add(_audit(request, admin, "source.delete", source, {"slug": source.slug}))
    await repo.delete(source)
