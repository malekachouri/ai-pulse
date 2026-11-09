"""Celery tasks. Each task runs its async body in a fresh event loop with a NullPool engine."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.ingestion.http import HttpClient
from app.ingestion.ratelimit import RedisRateLimiter
from app.ingestion.runner import run_source
from app.ingestion.scheduling import due_sources, recover_stale_jobs
from app.models.enums import JobStatus
from app.workers.celery_app import celery_app

log = get_logger(__name__)
T = TypeVar("T")


def _run[T](body: Callable[[async_sessionmaker[AsyncSession]], Awaitable[T]]) -> T:
    async def main() -> T:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            return await body(async_sessionmaker(engine, expire_on_commit=False))
        finally:
            await engine.dispose()

    return asyncio.run(main())


@celery_app.task(name="aipulse.ingest_source", bind=True, max_retries=None)
def ingest_source(self: Any, source_id: str, trigger: str = "schedule", attempt: int = 1) -> dict[str, Any]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    async def body(factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
        limiter = RedisRateLimiter(settings.redis_url)
        http = HttpClient(limiter=limiter)
        try:
            job = await run_source(
                factory,
                uuid.UUID(source_id),
                settings,
                http,
                trigger=trigger,
                attempt=attempt,
                task_id=self.request.id,
            )
        finally:
            await http.aclose()
            await limiter.close()
        if job is None:
            return {"status": "skipped"}
        return {"status": job.status.value, "job_id": str(job.id), "created": job.items_created}

    result = _run(body)
    if result.get("status") == JobStatus.FAILED.value and attempt < settings.ingestion_max_attempts:
        countdown = 60 * (2 ** (attempt - 1))  # 1 min, 2 min, 4 min …
        ingest_source.apply_async(
            args=[source_id], kwargs={"trigger": "retry", "attempt": attempt + 1}, countdown=countdown
        )
        result["retry_in_seconds"] = countdown
    return result


@celery_app.task(name="aipulse.dispatch_due_sources")
def dispatch_due_sources() -> int:
    async def body(factory: async_sessionmaker[AsyncSession]) -> list[str]:
        async with factory() as s:
            return [str(src.id) for src in await due_sources(s, datetime.now(UTC))]

    ids = _run(body)
    for sid in ids:
        ingest_source.delay(sid, "schedule")
    return len(ids)


@celery_app.task(name="aipulse.recover_stale_jobs")
def recover_stale() -> int:
    async def body(factory: async_sessionmaker[AsyncSession]) -> int:
        async with factory() as s:
            n = await recover_stale_jobs(s, datetime.now(UTC))
            await s.commit()
            return n

    return _run(body)
