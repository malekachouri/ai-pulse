"""Admin: system health, usage statistics, AI configuration and bulk retry of failed ingestion jobs."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import select

from app.api.deps import QueueDep, SessionDep, SettingsDep, StaffUser
from app.models import AuditLog, CollectionJob, Source
from app.models.enums import JobStatus
from app.schemas.common import ErrorResponse
from app.schemas.system import AIConfigView, BulkRetryResult, SystemHealth, UsageStats
from app.services.system import SystemService, ai_config

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


@router.get(
    "/system/health",
    response_model=SystemHealth,
    summary="Detailed health of every component (admin, analyst)",
    description="Database, migrations, Redis and queues, Celery Beat, workers, ingestion and AI provider.",
)
async def system_health(
    request: Request, session: SessionDep, settings: SettingsDep, _: StaffUser
) -> SystemHealth:
    return await SystemService(session, settings, getattr(request.app.state, "redis", None)).health()


@router.get("/usage", response_model=UsageStats, summary="Usage statistics over a window (admin, analyst)")
async def usage(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    _: StaffUser,
    days: int = Query(30, ge=7, le=90),
) -> UsageStats:
    return await SystemService(session, settings, getattr(request.app.state, "redis", None)).usage(days)


@router.get(
    "/ai/config",
    response_model=AIConfigView,
    summary="Effective AI provider configuration (no secrets)",
    description="AI providers are configured through environment variables only, so keys never transit the "
    "API or the database. This endpoint shows what is in effect and whether keys are present.",
)
async def get_ai_config(settings: SettingsDep, _: StaffUser) -> AIConfigView:
    return ai_config(settings)


@router.post(
    "/jobs/retry-failed",
    response_model=BulkRetryResult,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry every source whose latest job failed in the window (audited)",
    responses={503: {"model": ErrorResponse}},
)
async def retry_failed(
    request: Request,
    session: SessionDep,
    staff: StaffUser,
    queue: QueueDep,
    hours: int = Query(24, ge=1, le=168),
) -> BulkRetryResult:
    since = datetime.now(UTC) - timedelta(hours=hours)
    latest = (
        select(CollectionJob.source_id, CollectionJob.status)
        .distinct(CollectionJob.source_id)
        .where(CollectionJob.started_at >= since)
        .order_by(CollectionJob.source_id, CollectionJob.started_at.desc())
        .subquery()
    )
    sources = (
        await session.scalars(
            select(Source)
            .join(latest, latest.c.source_id == Source.id)
            .where(latest.c.status == JobStatus.FAILED)
        )
    ).all()
    task_ids, skipped = [], []
    for src in sources:
        if not src.enabled:
            skipped.append(src.slug)
            continue
        task_ids.append(queue.enqueue_ingest(str(src.id), "retry"))
    session.add(
        AuditLog(
            actor_id=staff.id,
            action="jobs.retry_failed",
            target_type="ingestion",
            target_id=None,
            details={"hours": hours, "retried": len(task_ids), "skipped": skipped},
            ip_address=request.client.host if request.client else None,
            created_at=datetime.now(UTC),
        )
    )
    return BulkRetryResult(retried=len(task_ids), task_ids=task_ids, skipped_sources=skipped)
