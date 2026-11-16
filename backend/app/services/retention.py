"""Retention: what the daily cleanup deletes (settings RETENTION_*; 0 keeps everything).

* Skills Radar entries that are no longer active (registry status deprecated or deleted, or removed from
  their marketplace) and not updated for RETENTION_INACTIVE_SKILLS_DAYS. Active entries are never deleted.
* Finished collection job logs older than RETENTION_JOBS_DAYS (pending and running jobs are kept).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import AISkill, CollectionJob
from app.models.enums import JobStatus

FINISHED = (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.PARTIAL)


@dataclass
class CleanupResult:
    skills_deleted: int = 0
    jobs_deleted: int = 0


async def cleanup(session: AsyncSession, settings: Settings, now: datetime) -> CleanupResult:
    out = CleanupResult()
    if settings.retention_inactive_skills_days:
        cutoff = now - timedelta(days=settings.retention_inactive_skills_days)
        last_change = func.coalesce(AISkill.source_updated_at, AISkill.last_seen_at)
        res = await session.execute(delete(AISkill).where(AISkill.status != "active", last_change < cutoff))
        out.skills_deleted = int(res.rowcount or 0)  # type: ignore[attr-defined]
    if settings.retention_jobs_days:
        cutoff = now - timedelta(days=settings.retention_jobs_days)
        res = await session.execute(
            delete(CollectionJob).where(
                CollectionJob.status.in_(FINISHED),
                func.coalesce(CollectionJob.finished_at, CollectionJob.started_at) < cutoff,
            )
        )
        out.jobs_deleted = int(res.rowcount or 0)  # type: ignore[attr-defined]
    return out
