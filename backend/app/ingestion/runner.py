"""Runs one source end to end and records a CollectionJob.

* A PostgreSQL advisory lock per source guarantees one concurrent run per source across all workers.
* Items, typed rows, checkpoint and job/health updates commit in ONE transaction: a crash never leaves a
  checkpoint advanced past data that wasn't saved (re-runs are idempotent).
* Failures are recorded on the job and the source (consecutive_failures drives backoff and health).
"""

import time
import uuid
from datetime import UTC, datetime

from prometheus_client import Counter, Histogram
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.ingestion.connectors import get_connector_class
from app.ingestion.http import FetchError, HttpClient
from app.models import CollectionJob, Source
from app.models.enums import JobStatus

log = get_logger(__name__)

RUNS = Counter("aipulse_ingestion_runs_total", "Ingestion runs", ["source", "status"])
ITEMS = Counter("aipulse_ingestion_items_total", "Ingested items", ["source", "outcome"])
DURATION = Histogram(
    "aipulse_ingestion_duration_seconds",
    "Ingestion run duration",
    ["source"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800),
)


def lock_key(source_id: uuid.UUID) -> int:
    """Signed 64-bit advisory-lock key derived from the source UUID."""
    k = source_id.int >> 64
    return k - (1 << 64) if k >= (1 << 63) else k


async def run_source(
    factory: async_sessionmaker[AsyncSession],
    source_id: uuid.UUID,
    settings: Settings,
    http: HttpClient,
    *,
    trigger: str = "schedule",
    attempt: int = 1,
    task_id: str | None = None,
    now: datetime | None = None,
) -> CollectionJob | None:
    """Return the finished job, or None if the source is missing, disabled (scheduled) or already running."""
    async with factory() as lock_session:
        conn = await lock_session.connection()
        got = await conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key(source_id)})
        if not got:
            log.info("ingestion_skipped_locked", source_id=str(source_id))
            return None
        try:
            return await _run_locked(factory, source_id, settings, http, trigger, attempt, task_id, now)
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key(source_id)})
            await lock_session.commit()


async def _run_locked(
    factory: async_sessionmaker[AsyncSession],
    source_id: uuid.UUID,
    settings: Settings,
    http: HttpClient,
    trigger: str,
    attempt: int,
    task_id: str | None,
    now: datetime | None,
) -> CollectionJob | None:
    started = now or datetime.now(UTC)
    async with factory() as s:
        source = await s.get(Source, source_id)
        if source is None or (not source.enabled and trigger == "schedule"):
            return None
        job = CollectionJob(
            id=uuid.uuid4(),
            source_id=source.id,
            status=JobStatus.RUNNING,
            trigger=trigger,
            attempt=attempt,
            celery_task_id=task_id,
            started_at=started,
        )
        s.add(job)
        await s.commit()
        job_id, slug = job.id, source.slug

    t0 = time.perf_counter()
    async with factory() as s:
        source = await s.get(Source, source_id)
        job = await s.get(CollectionJob, job_id)
        assert source is not None and job is not None
        try:
            connector = get_connector_class(source.connector)(source, http, settings)
            result = await connector.run(s, started)
        except Exception as exc:  # noqa: BLE001 - every failure is recorded, then surfaced via job status
            await s.rollback()
            source = await s.get(Source, source_id)
            job = await s.get(CollectionJob, job_id)
            assert source is not None and job is not None
            message = f"{type(exc).__name__}: {exc}"[:2000]
            job.status, job.error, job.finished_at = JobStatus.FAILED, message, datetime.now(UTC)
            if isinstance(exc, FetchError):
                job.errors = [{"stage": "fetch", "error": str(exc), "status": exc.status, "url": exc.url}]
            source.consecutive_failures += 1
            source.last_error, source.last_error_at = message, job.finished_at
            await s.commit()
            RUNS.labels(slug, "failed").inc()
            log.error("ingestion_failed", source=slug, error=message, attempt=attempt)
            return job
        finally:
            DURATION.labels(slug).observe(time.perf_counter() - t0)

        finished = datetime.now(UTC)
        job.items_fetched, job.items_created = result.fetched, result.created
        job.items_updated, job.items_skipped = result.updated, result.skipped + result.invalid
        job.errors = result.errors
        job.finished_at = finished
        if result.failed:  # every request failed: the source is down, even if the connector caught it
            job.status = JobStatus.FAILED
            job.error = f"all {len(result.errors)} fetch(es) failed: {result.errors[0]['error']}"[:2000]
            source.consecutive_failures += 1
            source.last_error, source.last_error_at = job.error, finished
        else:
            job.status = JobStatus.PARTIAL if result.partial else JobStatus.SUCCEEDED
            job.error = f"{len(result.errors)} record(s) failed" if result.partial else None
            if result.checkpoint is not None:
                source.checkpoint = result.checkpoint
            source.last_success_at = finished
            source.consecutive_failures = 0
        await s.commit()
        RUNS.labels(slug, job.status.value).inc()
        for outcome, n in (
            ("created", result.created),
            ("updated", result.updated),
            ("skipped", result.skipped),
            ("invalid", result.invalid),
        ):
            if n:
                ITEMS.labels(slug, outcome).inc(n)
        log.info(
            "ingestion_done",
            source=slug,
            status=job.status.value,
            fetched=result.fetched,
            created=result.created,
            updated=result.updated,
            invalid=result.invalid,
        )
        return job
