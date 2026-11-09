"""Which sources are due, stale-job recovery, and source health - all derived from the database, so admin
changes to `enabled` / `poll_interval_minutes` take effect on the next scheduler tick without restarts."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CollectionJob, Source
from app.models.enums import JobStatus

STALE_AFTER = timedelta(hours=1)
MAX_BACKOFF = timedelta(hours=24)


def next_due(source: Source, last_started: datetime | None) -> datetime | None:
    """Poll interval, doubled per consecutive failure (capped) so a broken source isn't hammered."""
    if last_started is None:
        return None
    interval = timedelta(minutes=source.poll_interval_minutes)
    if source.consecutive_failures:
        interval = min(interval * (2 ** min(source.consecutive_failures, 6)), max(MAX_BACKOFF, interval))
    return last_started + interval


async def _last_jobs(session: AsyncSession) -> dict:  # type: ignore[type-arg]
    rows = await session.execute(
        select(CollectionJob.source_id, func.max(CollectionJob.started_at)).group_by(CollectionJob.source_id)
    )
    return dict(rows.tuples().all())


async def due_sources(session: AsyncSession, now: datetime) -> list[Source]:
    sources = (await session.scalars(select(Source).where(Source.enabled.is_(True)))).all()
    last = await _last_jobs(session)
    running = set(
        await session.scalars(
            select(CollectionJob.source_id).where(
                CollectionJob.status == JobStatus.RUNNING, CollectionJob.started_at >= now - STALE_AFTER
            )
        )
    )
    out = []
    for s in sources:
        if s.id in running:
            continue
        due = next_due(s, last.get(s.id))
        if due is None or due <= now:
            out.append(s)
    return out


async def recover_stale_jobs(session: AsyncSession, now: datetime) -> int:
    jobs = (
        await session.scalars(
            select(CollectionJob).where(
                CollectionJob.status == JobStatus.RUNNING, CollectionJob.started_at < now - STALE_AFTER
            )
        )
    ).all()
    for job in jobs:
        job.status = JobStatus.FAILED
        job.finished_at = now
        job.error = "Worker lost: no completion within 60 minutes"
    return len(jobs)


@dataclass
class Health:
    status: str  # disabled | never_run | healthy | degraded | failing | stale
    reason: str


def source_health(source: Source, last_job: CollectionJob | None, now: datetime) -> Health:
    if not source.enabled:
        return Health("disabled", "Disabled by an administrator")
    if source.consecutive_failures >= 3:
        return Health("failing", f"{source.consecutive_failures} consecutive failed runs")
    if last_job is None and source.last_success_at is None:
        return Health("never_run", "Waiting for the first scheduled run")
    if source.consecutive_failures:
        return Health("degraded", "Last run failed; retrying with backoff")
    if last_job is not None and last_job.status == JobStatus.PARTIAL:
        return Health("degraded", "Last run skipped some invalid records")
    limit = timedelta(minutes=source.poll_interval_minutes * 3)
    if source.last_success_at is None or now - source.last_success_at > max(limit, timedelta(hours=1)):
        return Health("stale", "No successful run within 3 poll intervals")
    return Health("healthy", "Collecting normally")
