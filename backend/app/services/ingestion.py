from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.scheduling import next_due, source_health
from app.models import Article, CollectionJob, Source
from app.models.enums import JobStatus
from app.schemas.admin import CollectionJobOut
from app.schemas.ingestion import IngestionOverview, SourceStatus


def _job_out(j: CollectionJob) -> CollectionJobOut:
    out = CollectionJobOut.model_validate(j)
    if j.finished_at:
        out.duration_seconds = round((j.finished_at - j.started_at).total_seconds(), 3)
    return out


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def overview(self) -> IngestionOverview:
        now = datetime.now(UTC)
        sources = (await self.s.scalars(select(Source).order_by(Source.name))).all()
        latest_jobs = {
            j.source_id: j
            for j in await self.s.scalars(
                select(CollectionJob).order_by(CollectionJob.source_id, CollectionJob.started_at.desc())
                .distinct(CollectionJob.source_id)
            )
        }  # fmt: skip
        totals = dict(
            (await self.s.execute(select(Article.source_id, func.count()).group_by(Article.source_id)))
            .tuples()
            .all()
        )
        recent = dict(
            (
                await self.s.execute(
                    select(Article.source_id, func.count())
                    .where(Article.collected_at >= now - timedelta(hours=24))
                    .group_by(Article.source_id)
                )
            )
            .tuples()
            .all()
        )
        rows: list[SourceStatus] = []
        by_health: dict[str, int] = {}
        for src in sources:
            job = latest_jobs.get(src.id)
            h = source_health(src, job, now)
            by_health[h.status] = by_health.get(h.status, 0) + 1
            rows.append(
                SourceStatus(
                    id=src.id,
                    slug=src.slug,
                    name=src.name,
                    connector=src.connector,
                    source_type=src.source_type.value,
                    url=src.url,
                    enabled=src.enabled,
                    is_official=src.is_official,
                    poll_interval_minutes=src.poll_interval_minutes,
                    health=h.status,
                    health_reason=h.reason,
                    consecutive_failures=src.consecutive_failures,
                    last_success_at=src.last_success_at,
                    last_error_at=src.last_error_at,
                    last_error=src.last_error,
                    last_job=_job_out(job) if job else None,
                    next_run_at=(next_due(src, job.started_at if job else None) or now)
                    if src.enabled
                    else None,
                    items_total=totals.get(src.id, 0),
                    items_24h=recent.get(src.id, 0),
                )  # fmt: skip
            )
        failures = (
            await self.s.scalars(
                select(CollectionJob)
                .where(CollectionJob.status == JobStatus.FAILED)
                .order_by(CollectionJob.started_at.desc())
                .limit(20)
            )
        ).all()
        return IngestionOverview(
            generated_at=now,
            totals={
                "sources": len(sources),
                "enabled": sum(s.enabled for s in sources),
                "items": sum(totals.values()),
                "items_24h": sum(recent.values()),
            },  # fmt: skip
            by_health=by_health,
            sources=rows,
            recent_failures=[_job_out(j) for j in failures],
        )
