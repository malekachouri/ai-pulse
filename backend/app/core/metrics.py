"""Prometheus metrics.

* HTTP traffic (latency histogram, request counter) is measured in-process by `MetricsMiddleware`; route
  templates, never raw paths, are used as labels so cardinality stays bounded.
* Everything else is *derived state* collected at scrape time by `RuntimeCollector` from PostgreSQL and
  Redis (cached for a few seconds): DB pool and server connections, Celery queue lengths, ingestion jobs,
  source availability, AI calls / errors / tokens / cost, and Celery task durations. Task durations are
  recorded by the workers into Redis (see app/workers/telemetry.py) because worker processes cannot be
  scraped individually. This keeps one scrape target and no multi-process registry.
"""

import asyncio
import time
from collections.abc import Iterator
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily, Metric
from prometheus_client.registry import Collector
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

log = get_logger(__name__)

REQUESTS = Counter("aipulse_http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram(
    "aipulse_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
RATE_LIMITED = Counter("aipulse_rate_limited_total", "Requests rejected by the rate limiter", ["scope"])

# Celery task duration buckets (seconds); shared with app/workers/telemetry.py.
TASK_BUCKETS: tuple[float, ...] = (0.5, 1, 5, 15, 30, 60, 120, 300, 600, 1800)
TASK_STATS_KEY = "aipulse:metrics:tasks"
SCHEDULER_KEY = "aipulse:metrics:scheduler_last_dispatch"
BEAT_HEARTBEAT_KEY = "aipulse:metrics:beat_heartbeat"
QUEUES = ("ingestion",)


def route_template(request: Request) -> str:
    """Full route template (e.g. /api/v1/news/{article_id}) for the matched route, "unmatched" otherwise.

    FastAPI resolves included routers lazily, so the matched route only knows its path relative to its
    router; the full template comes from the routers' effective route contexts (mapped once per app).
    """
    route = request.scope.get("route")
    if route is None:
        return "unmatched"
    app = request.app
    paths: dict[int, str] | None = getattr(app.state, "_route_templates", None)
    if paths is None:
        paths = {}

        def walk(routes: Any) -> None:
            for r in routes:
                contexts = getattr(r, "effective_route_contexts", None)
                if callable(contexts):
                    for ctx in contexts():
                        original = getattr(ctx, "original_route", None)
                        paths[id(original)] = ctx.path_format
                        paths[id(ctx)] = ctx.path_format

        walk(app.routes)
        app.state._route_templates = paths
    return paths.get(id(route), getattr(route, "path_format", getattr(route, "path", "unmatched")))


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            label = route_template(request)
            LATENCY.labels(request.method, label).observe(time.perf_counter() - start)
            REQUESTS.labels(request.method, label, str(status)).inc()


def _families_from_task_stats(raw: dict[str, str]) -> list[Metric]:
    """Rebuild a histogram + failure counter from the flat Redis hash written by the workers."""
    tasks: dict[str, dict[str, float]] = {}
    for k, v in raw.items():
        task, _, field = k.rpartition("|")
        tasks.setdefault(task, {})[field] = float(v)
    hist = HistogramMetricFamily(
        "aipulse_celery_task_duration_seconds", "Celery task execution time", labels=["task"]
    )
    fails = CounterMetricFamily("aipulse_celery_task_failures", "Celery task failures", labels=["task"])
    retries = CounterMetricFamily("aipulse_celery_task_retries", "Celery task retries", labels=["task"])
    last = GaugeMetricFamily(
        "aipulse_celery_task_last_success_timestamp_seconds",
        "Unix time of the last successful run",
        labels=["task"],
    )
    for task, f in sorted(tasks.items()):
        buckets = [(str(float(b)), f.get(f"le_{b}", 0.0)) for b in TASK_BUCKETS]
        buckets.append(("+Inf", f.get("count", 0.0)))
        hist.add_metric([task], buckets, sum_value=f.get("sum", 0.0))
        fails.add_metric([task], f.get("failures", 0.0))
        retries.add_metric([task], f.get("retries", 0.0))
        if "last_success" in f:
            last.add_metric([task], f["last_success"])
    return [hist, fails, retries, last]


class RuntimeCollector(Collector):
    """Serves the latest snapshot; `refresh()` (async) rebuilds it at most every `ttl` seconds."""

    def __init__(self, ttl: float = 10.0) -> None:
        self.ttl = ttl
        self._families: list[Metric] = []
        self._at = 0.0
        self._lock = asyncio.Lock()

    def collect(self) -> Iterator[Metric]:
        yield from self._families

    async def refresh(self, app: Any) -> None:
        async with self._lock:
            if time.monotonic() - self._at < self.ttl:
                return
            fams: list[Metric] = []
            up = GaugeMetricFamily(
                "aipulse_dependency_up", "Dependency reachable from the API", labels=["name"]
            )
            try:
                fams += await self._database(app)
                up.add_metric(["postgres"], 1)
            except Exception as exc:  # noqa: BLE001 - a scrape must never fail; report the dependency as down
                log.warning("metrics_db_failed", error=type(exc).__name__)
                up.add_metric(["postgres"], 0)
            try:
                fams += await self._redis(app)
                up.add_metric(["redis"], 1)
            except Exception as exc:  # noqa: BLE001
                log.warning("metrics_redis_failed", error=type(exc).__name__)
                up.add_metric(["redis"], 0)
            fams.append(up)
            self._families, self._at = fams, time.monotonic()

    async def _database(self, app: Any) -> list[Metric]:
        fams: list[Metric] = []
        pool = app.state.engine.pool
        g = GaugeMetricFamily("aipulse_db_pool_connections", "SQLAlchemy pool connections", labels=["state"])
        for state, fn in (("checked_out", "checkedout"), ("idle", "checkedin"), ("size", "size")):
            if hasattr(pool, fn):
                g.add_metric([state], float(getattr(pool, fn)()))
        fams.append(g)
        async with app.state.session_factory() as s:
            conns = GaugeMetricFamily(
                "aipulse_db_connections", "PostgreSQL server connections to this database", labels=["state"]
            )
            for state, n in (
                await s.execute(
                    text(
                        "SELECT coalesce(state, 'unknown'), count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() GROUP BY 1"
                    )
                )
            ).all():
                conns.add_metric([state], n)
            fams.append(conns)
            maxc = await s.scalar(text("SELECT setting::int FROM pg_settings WHERE name = 'max_connections'"))
            fams.append(
                GaugeMetricFamily("aipulse_db_max_connections", "PostgreSQL max_connections", value=maxc)
            )

            jobs = CounterMetricFamily(
                "aipulse_ingestion_jobs", "Ingestion jobs by final status", labels=["status"]
            )
            for st, n in (
                await s.execute(text("SELECT status, count(*) FROM collection_jobs GROUP BY 1"))
            ).all():
                jobs.add_metric([st], n)
            fams.append(jobs)
            dur = GaugeMetricFamily(
                "aipulse_ingestion_job_duration_seconds_max_1h",
                "Longest finished ingestion job in the last hour",
                labels=["connector"],
            )
            for conn, sec in (
                await s.execute(
                    text(
                        "SELECT s.connector, max(extract(epoch FROM j.finished_at - j.started_at)) "
                        "FROM collection_jobs j JOIN sources s ON s.id = j.source_id "
                        "WHERE j.finished_at > now() - interval '1 hour' GROUP BY 1"
                    )
                )
            ).all():
                dur.add_metric([conn], float(sec or 0))
            fams.append(dur)

            src_up = GaugeMetricFamily(
                "aipulse_source_up",
                "1 = last run succeeded and it is not overdue (enabled sources only)",
                labels=["source", "connector"],
            )
            src_fail = GaugeMetricFamily(
                "aipulse_source_consecutive_failures", "Consecutive failed runs", labels=["source"]
            )
            src_last = GaugeMetricFamily(
                "aipulse_source_last_success_timestamp_seconds", "Last successful run", labels=["source"]
            )
            rows = (
                await s.execute(
                    text(
                        "SELECT slug, connector, consecutive_failures, extract(epoch FROM last_success_at), "
                        "last_success_at > now() - make_interval(mins => 3 * poll_interval_minutes + 10) "
                        "FROM sources WHERE enabled"
                    )
                )
            ).all()
            for slug, connector, failures, last_ok, fresh in rows:
                src_up.add_metric([slug, connector], 1.0 if failures == 0 and fresh else 0.0)
                src_fail.add_metric([slug], failures)
                if last_ok is not None:
                    src_last.add_metric([slug], float(last_ok))
            fams += [src_up, src_fail, src_last]

            calls = CounterMetricFamily(
                "aipulse_ai_calls",
                "LLM / embedding calls",
                labels=["provider", "model", "purpose", "outcome"],
            )
            tokens = CounterMetricFamily(
                "aipulse_ai_tokens", "Tokens used", labels=["provider", "model", "direction"]
            )
            cost = CounterMetricFamily(
                "aipulse_ai_cost_usd", "Estimated cost (USD)", labels=["provider", "model"]
            )
            for prov, model, purpose, ok, n, tin, tout, usd in (
                await s.execute(
                    text(
                        "SELECT provider, model, purpose, ok, count(*), sum(input_tokens), "
                        "sum(output_tokens), coalesce(sum(cost_usd), 0) FROM ai_usage GROUP BY 1, 2, 3, 4"
                    )
                )
            ).all():
                calls.add_metric([prov, model, purpose, "ok" if ok else "error"], n)
                tokens.add_metric([prov, model, "input"], float(tin or 0))
                tokens.add_metric([prov, model, "output"], float(tout or 0))
                cost.add_metric([prov, model], float(usd or 0))
            fams += [calls, tokens, cost]

            for name, sql, doc in (
                ("aipulse_users", "SELECT count(*) FROM users WHERE is_active", "Active user accounts"),
                ("aipulse_articles", "SELECT count(*) FROM articles", "Collected items"),
                (
                    "aipulse_articles_unanalysed",
                    "SELECT count(*) FROM articles a WHERE NOT EXISTS "
                    "(SELECT 1 FROM ai_analyses x WHERE x.article_id = a.id)",
                    "Items waiting for AI analysis",
                ),
            ):
                fams.append(GaugeMetricFamily(name, doc, value=float(await s.scalar(text(sql)) or 0)))
        return fams

    async def _redis(self, app: Any) -> list[Metric]:
        r = app.state.redis
        q = GaugeMetricFamily(
            "aipulse_celery_queue_length", "Messages waiting in a Celery queue", labels=["queue"]
        )
        for name in QUEUES:
            q.add_metric([name], float(await r.llen(name)))
        fams: list[Metric] = [q]
        raw = await r.hgetall(TASK_STATS_KEY)
        fams += _families_from_task_stats({k.decode(): v.decode() for k, v in raw.items()})
        beat = await r.get(BEAT_HEARTBEAT_KEY)
        if beat is not None:
            fams.append(
                GaugeMetricFamily(
                    "aipulse_beat_heartbeat_timestamp_seconds",
                    "Unix time of the last Celery Beat scheduler loop",
                    value=float(beat),
                )
            )
        last = await r.get(SCHEDULER_KEY)
        if last is not None:
            fams.append(
                GaugeMetricFamily(
                    "aipulse_scheduler_last_dispatch_timestamp_seconds",
                    "Unix time Celery Beat last dispatched due sources",
                    value=float(last),
                )
            )
        return fams


RUNTIME = RuntimeCollector()
REGISTRY.register(RUNTIME)


async def metrics_response(app: Any) -> Response:
    await RUNTIME.refresh(app)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
