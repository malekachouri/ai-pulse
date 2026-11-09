import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from pydantic import ValidationError

from app.api.deps import AdminUser, QueueDep, SessionDep, StaffUser
from app.core.errors import AppError, ConflictError, NotFoundError
from app.ingestion.connectors import REGISTRY
from app.models import AuditLog, CollectionJob, Source
from app.models.enums import JobStatus
from app.repositories.sources import SourceRepository
from app.schemas.admin import (
    AdminUserFilters,
    AdminUserOut,
    AdminUserUpdate,
    AuditFilters,
    AuditLogOut,
    CollectionJobOut,
    JobFilters,
    RoleOut,
)
from app.schemas.common import ErrorResponse, Page
from app.schemas.ingestion import ConnectorInfo, EnqueueResponse, IngestionOverview
from app.schemas.source import SourceCreate, SourceOut, SourceUpdate
from app.services.admin import AdminService
from app.services.ingestion import IngestionService

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


def _validated_config(connector: str, config: dict | None) -> dict:
    """Reject unknown connectors and invalid connector options before they reach a worker."""
    cls = REGISTRY.get(connector)
    if cls is None:
        raise AppError(f"Unknown connector '{connector}'", details={"available": sorted(REGISTRY)})
    try:
        return cls.Config.model_validate(config or {}).model_dump(mode="json", exclude_unset=True)
    except ValidationError as exc:
        details = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        raise AppError(f"Invalid configuration for connector '{connector}'", details=details) from exc


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
    data["config"] = _validated_config(body.connector, body.config)
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
    if changes.pop("reset_checkpoint", False):
        source.checkpoint = {}
        changes["checkpoint_reset"] = True
    if "config" in changes:
        changes["config"] = _validated_config(source.connector, changes["config"])
    for key, value in changes.items():
        if key != "checkpoint_reset":
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


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/users", response_model=Page[AdminUserOut])
async def list_users(
    session: SessionDep, _: AdminUser, f: Annotated[AdminUserFilters, Query()]
) -> Page[AdminUserOut]:
    return await AdminService(session).list_users(f)


@router.get("/users/{user_id}", response_model=AdminUserOut, responses={404: {"model": ErrorResponse}})
async def get_user(user_id: uuid.UUID, session: SessionDep, _: AdminUser) -> AdminUserOut:
    return AdminUserOut.model_validate(await AdminService(session).get_user(user_id))


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserOut,
    summary="Change a user's role or active status (audited)",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def update_user(
    user_id: uuid.UUID, body: AdminUserUpdate, request: Request, session: SessionDep, admin: AdminUser
) -> AdminUserOut:
    return await AdminService(session).update_user(admin, user_id, body, _ip(request))


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(session: SessionDep, _: AdminUser) -> list[RoleOut]:
    return await AdminService(session).roles()


@router.get("/jobs", response_model=Page[CollectionJobOut], summary="Ingestion job history (admin, analyst)")
async def list_jobs(
    session: SessionDep, _: StaffUser, f: Annotated[JobFilters, Query()]
) -> Page[CollectionJobOut]:
    return await AdminService(session).jobs(f)


@router.get("/audit-logs", response_model=Page[AuditLogOut])
async def list_audit_logs(
    session: SessionDep, _: AdminUser, f: Annotated[AuditFilters, Query()]
) -> Page[AuditLogOut]:
    return await AdminService(session).audit_logs(f)


# ------------------------------------------------------------------ ingestion
@router.get(
    "/connectors", response_model=list[ConnectorInfo], summary="Available connectors and their options"
)
async def list_connectors(_: StaffUser) -> list[ConnectorInfo]:
    return [
        ConnectorInfo(key=k, description=c.description, config_schema=c.Config.model_json_schema())
        for k, c in sorted(REGISTRY.items())
    ]


@router.get(
    "/ingestion/status", response_model=IngestionOverview, summary="Source health and recent failures"
)
async def ingestion_status(session: SessionDep, _: StaffUser) -> IngestionOverview:
    return await IngestionService(session).overview()


@router.post(
    "/sources/{source_id}/run",
    response_model=EnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an immediate run (works for disabled sources too)",
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def run_source_now(
    source_id: uuid.UUID, request: Request, session: SessionDep, staff: StaffUser, queue: QueueDep
) -> EnqueueResponse:
    source = await SourceRepository(session).get(source_id)
    if source is None:
        raise NotFoundError("Source not found")
    task_id = queue.enqueue_ingest(str(source.id), "manual")
    session.add(_audit(request, staff, "source.run", source, {"task_id": task_id}))
    return EnqueueResponse(task_id=task_id, source_id=source.id)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=EnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def retry_job(
    job_id: uuid.UUID, request: Request, session: SessionDep, staff: StaffUser, queue: QueueDep
) -> EnqueueResponse:
    job = await session.get(CollectionJob, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    if job.status not in (JobStatus.FAILED, JobStatus.PARTIAL):
        raise ConflictError(f"Only failed or partial jobs can be retried (this one is {job.status.value})")
    source = await session.get(Source, job.source_id)
    assert source is not None
    task_id = queue.enqueue_ingest(str(source.id), "retry")
    session.add(_audit(request, staff, "job.retry", source, {"job_id": str(job.id), "task_id": task_id}))
    return EnqueueResponse(task_id=task_id, source_id=source.id)
