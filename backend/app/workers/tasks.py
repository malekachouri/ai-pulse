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
    if result.get("created"):
        ai_analyze.delay()  # analyse new items promptly instead of waiting for the next tick
    if result.get("status") in ("succeeded", "partial"):
        evaluate_alerts.delay()
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

    from app.workers.telemetry import mark_scheduler_dispatch

    ids = _run(body)
    for sid in ids:
        ingest_source.delay(sid, "schedule")
    mark_scheduler_dispatch()  # lets Prometheus alert when Beat stops dispatching
    return len(ids)


@celery_app.task(name="aipulse.recover_stale_jobs")
def recover_stale() -> int:
    async def body(factory: async_sessionmaker[AsyncSession]) -> int:
        async with factory() as s:
            n = await recover_stale_jobs(s, datetime.now(UTC))
            await s.commit()
            return n

    return _run(body)


@celery_app.task(name="aipulse.ai_analyze")
def ai_analyze() -> dict[str, Any]:
    """Deterministic analysis for every new item; embeddings and LLM analysis when configured (budgeted)."""
    from app.ai.pipeline import AnalysisPipeline
    from app.ai.providers import build_providers

    settings = get_settings()

    async def body(factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
        providers = build_providers(settings)
        try:
            async with factory() as s:
                stats = await AnalysisPipeline(s, providers, daily_budget=settings.ai_daily_token_budget).run(
                    llm_limit=settings.ai_batch_size
                )
                await s.commit()
        finally:
            await providers.aclose()
        return {k: v for k, v in stats.__dict__.items() if k != "errors"} | {"errors": len(stats.errors)}

    return _run(body)


@celery_app.task(name="aipulse.ai_rescore")
def ai_rescore() -> int:
    """Recompute importance for the last 14 days (recency decays; KEV/incident status changes)."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.ai.pipeline import AnalysisPipeline
    from app.ai.providers import AIProviders
    from app.models import Article

    async def body(factory: async_sessionmaker[AsyncSession]) -> int:
        async with factory() as s:
            pipe = AnalysisPipeline(s, AIProviders(None, None))
            since = datetime.now(UTC) - timedelta(days=14)
            n = 0
            for a in (await s.scalars(select(Article).where(Article.collected_at >= since))).unique():
                await pipe.score(a)
                n += 1
            await s.commit()
            return n

    return _run(body)


@celery_app.task(name="aipulse.generate_due_briefings")
def generate_due_briefings() -> int:
    """Fan out: one `generate_briefing` task per due (user, local date). Re-dispatching the same pair is
    harmless - generation is idempotent - so a slow worker never causes duplicate briefings."""
    from app.ai.briefing import due_briefings

    async def body(factory: async_sessionmaker[AsyncSession]) -> int:
        async with factory() as s:
            due = await due_briefings(s, datetime.now(UTC))
        for d in due:
            generate_briefing.delay(str(d.user_id) if d.user_id else None, d.local_date.isoformat())
        return len(due)

    return _run(body)


@celery_app.task(
    name="aipulse.generate_briefing",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=900,
    retry_jitter=True,
    max_retries=get_settings().briefing_max_retries,
)
def generate_briefing(self: Any, user_id: str | None, local_date: str) -> dict[str, Any]:
    from datetime import date

    from app.ai.briefing import run_scheduled_briefing
    from app.ai.providers import build_providers

    settings = get_settings()

    async def body(factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
        providers = build_providers(settings)
        try:
            async with factory() as s:
                b, notified = await run_scheduled_briefing(
                    s,
                    providers,
                    uuid.UUID(user_id) if user_id else None,
                    date.fromisoformat(local_date),
                    datetime.now(UTC),
                )
                await s.commit()
        finally:
            await providers.aclose()
        bid = str(b.id) if b else None
        return {"briefing_id": bid, "notified": notified, "attempt": self.request.retries}

    return _run(body)


@celery_app.task(name="aipulse.evaluate_alerts")
def evaluate_alerts() -> dict[str, Any]:
    from app.alerts.engine import AlertEngine

    async def body(factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
        async with factory() as s:
            stats = await AlertEngine(s).run()
            await s.commit()
            return {"created": stats.created, "by_rule": stats.by_rule}

    return _run(body)
