"""Admin: system health checks and usage statistics (read-only, aggregate queries)."""

import platform
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Date, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.metrics import QUEUES, SCHEDULER_KEY, TASK_STATS_KEY
from app.models import (
    AIUsage,
    Article,
    Bookmark,
    CollectionJob,
    DailyBriefing,
    Notification,
    Role,
    Source,
    User,
)
from app.models.enums import JobStatus
from app.schemas.system import (
    AIConfigView,
    AIUsageDay,
    AIUsageRow,
    Check,
    DayValue,
    SystemHealth,
    UsageStats,
)

STARTED_AT = datetime.now(UTC)
VERSION = "0.8.0"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _worst(statuses: list[str]) -> str:
    return "down" if "down" in statuses else "degraded" if "degraded" in statuses else "ok"


def alembic_head() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
        return ScriptDirectory.from_config(cfg).get_current_head()
    except Exception:  # noqa: BLE001 - reported as unknown
        return None


class SystemService:
    def __init__(self, session: AsyncSession, settings: Settings, redis: Any | None) -> None:
        self.s = session
        self.settings = settings
        self.redis = redis

    async def health(self) -> SystemHealth:
        now = datetime.now(UTC)
        checks = [
            await self._database(),
            await self._migrations(),
            *await self._redis_checks(now),
            await self._ingestion(now),
            await self._ai(now),
        ]
        return SystemHealth(
            status=_worst([c.status for c in checks]),  # type: ignore[arg-type]
            environment=self.settings.environment,
            version=VERSION,
            started_at=STARTED_AT,
            checked_at=now,
            checks=checks,
        )

    async def _database(self) -> Check:
        t = time.perf_counter()
        try:
            version = await self.s.scalar(text("SHOW server_version"))
            vector = await self.s.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
            size = await self.s.scalar(text("SELECT pg_database_size(current_database())"))
            conns = await self.s.scalar(
                text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
            )
            maxc = await self.s.scalar(text("SHOW max_connections"))
        except Exception as exc:  # noqa: BLE001
            return Check(name="database", status="down", detail=type(exc).__name__)
        ms = round((time.perf_counter() - t) * 1000, 1)
        usage = int(conns or 0) / max(1, int(maxc or 100))
        status = "ok" if vector and usage < 0.8 else "degraded"
        detail = None if vector else "pgvector extension missing"
        if usage >= 0.8:
            detail = f"{int(usage * 100)}% of max_connections in use"
        return Check(
            name="database",
            status=status,  # type: ignore[arg-type]
            detail=detail,
            latency_ms=ms,
            data={
                "postgres": version,
                "pgvector": vector,
                "size_bytes": int(size or 0),
                "connections": int(conns or 0),
                "max_connections": int(maxc or 0),
                "python": platform.python_version(),
            },
        )

    async def _migrations(self) -> Check:
        try:
            current = await self.s.scalar(text("SELECT version_num FROM alembic_version"))
        except Exception as exc:  # noqa: BLE001
            return Check(name="migrations", status="down", detail=type(exc).__name__)
        head = alembic_head()
        ok = head is not None and current == head
        return Check(
            name="migrations",
            status="ok" if ok else "degraded",
            detail=None if ok else f"database at {current}, code expects {head}",
            data={"current": current, "head": head},
        )

    async def _redis_checks(self, now: datetime) -> list[Check]:
        if self.redis is None:
            return [Check(name="redis", status="down", detail="not configured")]
        t = time.perf_counter()
        try:
            await self.redis.ping()
            ms = round((time.perf_counter() - t) * 1000, 1)
            info = await self.redis.info("memory")
            queues = {q: int(await self.redis.llen(q)) for q in QUEUES}
            last_dispatch = await self.redis.get(SCHEDULER_KEY)
            raw = await self.redis.hgetall(TASK_STATS_KEY)
        except Exception as exc:  # noqa: BLE001
            return [Check(name="redis", status="down", detail=type(exc).__name__)]
        stats = {k.decode(): float(v) for k, v in raw.items()}
        backlog = sum(queues.values())
        redis_check = Check(
            name="redis",
            status="ok" if backlog < 500 else "degraded",
            detail=None if backlog < 500 else f"{backlog} tasks waiting",
            latency_ms=ms,
            data={"used_memory": info.get("used_memory_human"), "queues": queues},
        )
        max_age = 3 * self.settings.ingestion_dispatch_seconds + 60
        if last_dispatch is None:
            sched = Check(name="scheduler", status="degraded", detail="Celery Beat has not dispatched yet")
        else:
            at = datetime.fromtimestamp(float(last_dispatch), UTC)
            age = (now - at).total_seconds()
            sched = Check(
                name="scheduler",
                status="ok" if age <= max_age else "down",
                detail=None if age <= max_age else f"no dispatch for {int(age)} s",
                data={"last_dispatch_at": at.isoformat()},
            )
        tasks: dict[str, dict[str, float]] = {}
        for k, v in stats.items():
            task, _, field = k.rpartition("|")
            if field in ("count", "failures", "last_success"):
                tasks.setdefault(task, {})[field] = v
        last_ok = max((t.get("last_success", 0) for t in tasks.values()), default=0)
        age = (now.timestamp() - last_ok) if last_ok else None
        workers = Check(
            name="workers",
            status="ok" if age is not None and age < 15 * 60 else "degraded",
            detail=None if age is not None and age < 15 * 60 else "no task completed in the last 15 minutes",
            data={
                "last_task_success_at": datetime.fromtimestamp(last_ok, UTC).isoformat() if last_ok else None,
                "tasks": {
                    name: {"runs": int(t.get("count", 0)), "failures": int(t.get("failures", 0))}
                    for name, t in sorted(tasks.items())
                },
            },
        )
        return [redis_check, sched, workers]

    async def _ingestion(self, now: datetime) -> Check:
        enabled = await self.s.scalar(select(func.count(Source.id)).where(Source.enabled.is_(True))) or 0
        failing = (
            await self.s.scalars(
                select(Source.slug).where(Source.enabled.is_(True), Source.consecutive_failures > 0)
            )
        ).all()
        failed_24h = (
            await self.s.scalar(
                select(func.count(CollectionJob.id)).where(
                    CollectionJob.status == JobStatus.FAILED,
                    CollectionJob.started_at >= now - timedelta(hours=24),
                )
            )
            or 0
        )
        running = (
            await self.s.scalar(
                select(func.count(CollectionJob.id)).where(CollectionJob.status == JobStatus.RUNNING)
            )
            or 0
        )
        ratio = len(failing) / enabled if enabled else 0
        status = "ok" if ratio == 0 else "degraded" if ratio < 0.5 else "down"
        return Check(
            name="ingestion",
            status=status,  # type: ignore[arg-type]
            detail=f"{len(failing)} of {enabled} sources failing" if failing else None,
            data={
                "enabled_sources": enabled,
                "failing_sources": list(failing),
                "failed_jobs_24h": failed_24h,
                "running_jobs": running,
            },
        )

    async def _ai(self, now: datetime) -> Check:
        row = (
            await self.s.execute(
                select(func.count(AIUsage.id), func.count(AIUsage.id).filter(AIUsage.ok.is_(False))).where(
                    AIUsage.created_at >= now - timedelta(hours=24)
                )
            )
        ).one()
        calls, errors = int(row[0]), int(row[1])
        configured = self.settings.llm_provider != "none"
        rate = errors / calls if calls else 0
        status = "ok" if rate < 0.2 else "degraded"
        return Check(
            name="ai_provider",
            status=status,  # type: ignore[arg-type]
            detail=(None if configured else "no LLM configured (deterministic analysis only)")
            if status == "ok"
            else f"{int(rate * 100)}% of AI calls failed in 24 h",
            data={"provider": self.settings.llm_provider, "calls_24h": calls, "errors_24h": errors},
        )

    # ------------------------------------------------------------------ usage
    async def usage(self, days: int) -> UsageStats:
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        async def per_day(col: Any, *where: Any) -> list[DayValue]:
            d = cast(func.date_trunc("day", col), Date)
            rows = (
                await self.s.execute(select(d, func.count()).where(col >= since, *where).group_by(d))
            ).all()
            got = {r[0]: r[1] for r in rows}
            return [
                DayValue(day=day, value=float(got.get(day, 0)))
                for day in (since.date() + timedelta(days=i) for i in range(days + 1))
            ]

        async def scalar(stmt: Any) -> int:
            return int(await self.s.scalar(stmt) or 0)

        by_role = dict(
            (r.value, n)
            for r, n in (
                await self.s.execute(select(Role.name, func.count(User.id)).join(User).group_by(Role.name))
            ).all()
        )
        by_type = {
            t.value: n
            for t, n in (
                await self.s.execute(select(Article.item_type, func.count()).group_by(Article.item_type))
            ).all()
        }
        by_kind = {
            k.value: n
            for k, n in (
                await self.s.execute(
                    select(Notification.kind, func.count())
                    .where(Notification.created_at >= since)
                    .group_by(Notification.kind)
                )
            ).all()
        }
        n_total = sum(by_kind.values())
        n_read = await scalar(
            select(func.count()).where(Notification.created_at >= since, Notification.read_at.is_not(None))
        )
        d = cast(func.date_trunc("day", AIUsage.created_at), Date)
        ai_days = {
            r[0]: r
            for r in (
                await self.s.execute(
                    select(
                        d,
                        func.count(),
                        func.count().filter(AIUsage.ok.is_(False)),
                        func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0),
                        func.sum(AIUsage.cost_usd),
                    )
                    .where(AIUsage.created_at >= since)
                    .group_by(d)
                )
            ).all()
        }
        ai_by_day = []
        for i in range(days + 1):
            day: date = since.date() + timedelta(days=i)
            r = ai_days.get(day)
            ai_by_day.append(
                AIUsageDay(
                    day=day,
                    calls=int(r[1]) if r else 0,
                    errors=int(r[2]) if r else 0,
                    tokens=int(r[3]) if r else 0,
                    cost_usd=float(r[4]) if r and r[4] is not None else None,
                )
            )
        models = [
            AIUsageRow(
                provider=p,
                model=m,
                purpose=pu,
                calls=int(c),
                errors=int(e),
                input_tokens=int(i or 0),
                output_tokens=int(o or 0),
                cost_usd=float(cost) if cost is not None else None,
            )
            for p, m, pu, c, e, i, o, cost in (
                await self.s.execute(
                    select(
                        AIUsage.provider,
                        AIUsage.model,
                        AIUsage.purpose,
                        func.count(),
                        func.count().filter(AIUsage.ok.is_(False)),
                        func.sum(AIUsage.input_tokens),
                        func.sum(AIUsage.output_tokens),
                        func.sum(AIUsage.cost_usd),
                    )
                    .where(AIUsage.created_at >= since)
                    .group_by(AIUsage.provider, AIUsage.model, AIUsage.purpose)
                    .order_by(func.count().desc())
                )
            ).all()
        ]
        costs = [m.cost_usd for m in models if m.cost_usd is not None]
        return UsageStats(
            window_days=days,
            generated_at=now,
            users_total=await scalar(select(func.count(User.id))),
            users_active=await scalar(select(func.count(User.id)).where(User.is_active.is_(True))),
            users_by_role=by_role,
            users_new=await scalar(select(func.count(User.id)).where(User.created_at >= since)),
            users_logged_in_7d=await scalar(
                select(func.count(User.id)).where(User.last_login_at >= now - timedelta(days=7))
            ),
            signups_by_day=await per_day(User.created_at),
            articles_total=await scalar(select(func.count(Article.id))),
            articles_by_day=await per_day(Article.collected_at),
            articles_by_type=by_type,
            bookmarks_total=await scalar(select(func.count(Bookmark.id))),
            notifications_by_day=await per_day(Notification.created_at),
            notifications_by_kind=by_kind,
            notifications_read_ratio=round(n_read / n_total, 3) if n_total else None,
            briefings_by_day=await per_day(DailyBriefing.generated_at),
            ai_by_day=ai_by_day,
            ai_by_model=models,
            ai_tokens_total=sum(m.input_tokens + m.output_tokens for m in models),
            ai_cost_total_usd=round(sum(costs), 6) if costs else None,
            ai_daily_token_budget=self.settings.ai_daily_token_budget,
        )


def ai_config(settings: Settings) -> AIConfigView:
    return AIConfigView(
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_dim=settings.embedding_dim,
        openai_base_url=settings.openai_base_url,
        anthropic_api_url=settings.anthropic_api_url,
        ollama_base_url=settings.ollama_base_url,
        openai_api_key_set=settings.openai_api_key is not None,
        anthropic_api_key_set=settings.anthropic_api_key is not None,
        llm_timeout_seconds=settings.llm_timeout_seconds,
        llm_max_output_tokens=settings.llm_max_output_tokens,
        llm_temperature=settings.llm_temperature,
        llm_price_input_per_mtok=settings.llm_price_input_per_mtok,
        llm_price_output_per_mtok=settings.llm_price_output_per_mtok,
        ai_batch_size=settings.ai_batch_size,
        ai_daily_token_budget=settings.ai_daily_token_budget,
    )
