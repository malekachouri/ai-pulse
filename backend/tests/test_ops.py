"""Phase 8: rate limiting, metrics endpoint/collectors, worker telemetry and production config guards."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError

from app.core import metrics as m
from app.core.config import Settings
from app.core.ratelimit import InMemoryLimiter, Limit
from app.db.session import create_engine
from app.main import create_app
from app.models import AIUsage, CollectionJob, Source
from app.models.enums import ItemType, JobStatus, SourceType
from app.workers import telemetry
from tests.conftest import PASSWORD, register_and_login


class FakeAsyncRedis:
    def __init__(self, hash_: dict[bytes, bytes] | None = None) -> None:
        self.hash = hash_ or {}

    async def llen(self, name: str) -> int:
        return 7 if name == "ingestion" else 0

    async def hgetall(self, key: str) -> dict[bytes, bytes]:
        return self.hash

    async def get(self, key: str) -> bytes | None:
        return b"1762700000.0"


class FakePipe:
    def __init__(self, store: dict[str, float]) -> None:
        self.store, self.ops = store, []

    def hincrby(self, _k: str, f: str, n: int) -> None:
        self.ops.append((f, n))

    hincrbyfloat = hincrby

    def hset(self, _k: str, f: str, v: float) -> None:
        self.ops.append((f, None, v))

    def execute(self) -> None:
        for op in self.ops:
            if len(op) == 3:
                self.store[op[0]] = op[2]
            else:
                self.store[op[0]] = self.store.get(op[0], 0) + op[1]


class FakeSyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, float] = {}

    def pipeline(self, transaction: bool = False) -> FakePipe:
        return FakePipe(self.store)


def _app(settings: Settings, session_factory, **over):  # type: ignore[no-untyped-def]
    app = create_app(settings.model_copy(update=over))
    app.state.session_factory = session_factory
    app.state.rate_limiter = InMemoryLimiter()
    return app


# ------------------------------------------------------------------ rate limiting
def test_limit_parsing():
    assert Limit.parse("10/minute") == Limit(10, 60)
    assert Limit.parse(" 5 / hour ") == Limit(5, 3600)
    for bad in ("10", "ten/minute", "10/day", ""):
        with pytest.raises(ValueError):
            Limit.parse(bad)
    with pytest.raises(ValidationError):
        Settings(rate_limit_auth="lots")


async def test_auth_endpoints_are_rate_limited_per_ip(settings, session_factory):
    app = _app(settings, session_factory, rate_limit_enabled=True, rate_limit_auth="3/minute")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        codes = []
        for _ in range(4):
            r = await c.post("/api/v1/auth/login", json={"email": "x@example.com", "password": PASSWORD})
            codes.append(r.status_code)
        assert codes == [401, 401, 401, 429]
        assert r.json()["error"]["code"] == "rate_limited"
        assert int(r.headers["Retry-After"]) >= 1
        assert r.json()["error"]["details"]["retry_after_seconds"] >= 1
        # other scopes are independent
        assert (await c.get("/api/v1/news")).status_code == 200


async def test_global_and_per_user_limits(settings, session_factory):
    app = _app(
        settings,
        session_factory,
        rate_limit_enabled=True,
        rate_limit_global="6/minute",
        rate_limit_search="2/minute",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/search", params={"q": "kubernetes"})
        assert r.status_code == 200 and r.headers["X-RateLimit-Limit"] == "2"
        assert r.headers["X-RateLimit-Remaining"] == "1"
        await c.get("/api/v1/search", params={"q": "kubernetes"})
        assert (await c.get("/api/v1/search", params={"q": "kubernetes"})).status_code == 429
        for _ in range(3):
            await c.get("/api/v1/categories")
        r = await c.get("/api/v1/categories")  # 7th /api/v1 request from this IP
        assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
        assert (await c.get("/health/live")).status_code == 200  # probes are never limited


async def test_limiter_fails_open_when_backend_is_down(settings, session_factory):
    class Broken:
        async def hit(self, key: str, period: int) -> int:
            raise ConnectionError("redis down")

    app = _app(settings, session_factory, rate_limit_enabled=True, rate_limit_global="1/minute")
    app.state.rate_limiter = Broken()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        codes = [(await c.get("/api/v1/categories")).status_code for _ in range(3)]
        assert codes == [200, 200, 200]


# ------------------------------------------------------------------ metrics
@pytest.fixture
async def metrics_app(settings, session_factory):
    m.RUNTIME._at = 0.0  # bypass the scrape cache between tests
    app = _app(settings, session_factory, metrics_token=SecretStr("s3cret-metrics-token"))
    engine = create_engine(settings)
    app.state.engine = engine
    stats = {
        b"aipulse.ingest_source|count": b"3",
        b"aipulse.ingest_source|sum": b"42.5",
        b"aipulse.ingest_source|le_5": b"1",
        b"aipulse.ingest_source|le_30": b"3",
        b"aipulse.ingest_source|failures": b"1",
        b"aipulse.ingest_source|last_success": b"1762700000",
    }
    app.state.redis = FakeAsyncRedis(stats)
    async with session_factory() as s:
        src = Source(slug="flaky", name="Flaky", source_type=SourceType.RSS, connector="rss",
                     url="https://f.test/feed", default_item_type=ItemType.NEWS, consecutive_failures=2)  # fmt: skip
        ok = Source(slug="healthy", name="Healthy", source_type=SourceType.RSS, connector="rss",
                    url="https://h.test/feed", default_item_type=ItemType.NEWS,
                    last_success_at=datetime.now(UTC))  # fmt: skip
        s.add_all([src, ok])
        await s.flush()
        now = datetime.now(UTC)
        s.add(CollectionJob(source_id=src.id, status=JobStatus.FAILED, started_at=now - timedelta(seconds=30),
                            finished_at=now, error="boom"))  # fmt: skip
        s.add_all(
            [
                AIUsage(
                    purpose="analysis",
                    provider="openai",
                    model="m1",
                    input_tokens=1000,
                    output_tokens=200,
                    cost_usd=0.01,
                    ok=True,
                    created_at=now,
                ),  # fmt: skip
                AIUsage(
                    purpose="analysis",
                    provider="openai",
                    model="m1",
                    ok=False,
                    error="timeout",
                    created_at=now,
                ),  # fmt: skip
            ]
        )
        await s.commit()
    yield app
    await engine.dispose()


async def test_metrics_require_token_and_expose_runtime_state(metrics_app):
    async with AsyncClient(transport=ASGITransport(app=metrics_app), base_url="http://test") as c:
        assert (await c.get("/metrics")).status_code == 401
        assert (await c.get("/metrics", headers={"Authorization": "Bearer wrong"})).status_code == 401
        await c.get("/api/v1/categories")
        r = await c.get("/metrics", headers={"Authorization": "Bearer s3cret-metrics-token"})
    assert r.status_code == 200
    body = r.text
    expected = [
        'aipulse_http_requests_total{method="GET",route="/api/v1/categories",status="200"}',
        'aipulse_dependency_up{name="postgres"} 1.0',
        'aipulse_dependency_up{name="redis"} 1.0',
        'aipulse_celery_queue_length{queue="ingestion"} 7.0',
        'aipulse_source_up{connector="rss",source="flaky"} 0.0',
        'aipulse_source_up{connector="rss",source="healthy"} 1.0',
        'aipulse_source_consecutive_failures{source="flaky"} 2.0',
        'aipulse_ingestion_jobs_total{status="failed"} 1.0',
        'aipulse_ai_calls_total{model="m1",outcome="error",provider="openai",purpose="analysis"} 1.0',
        'aipulse_ai_tokens_total{direction="input",model="m1",provider="openai"} 1000.0',
        'aipulse_ai_cost_usd_total{model="m1",provider="openai"} 0.01',
        'aipulse_celery_task_duration_seconds_bucket{le="30.0",task="aipulse.ingest_source"} 3.0',
        'aipulse_celery_task_duration_seconds_count{task="aipulse.ingest_source"} 3.0',
        'aipulse_celery_task_failures_total{task="aipulse.ingest_source"} 1.0',
        "aipulse_scheduler_last_dispatch_timestamp_seconds 1.7627e+09",
        "aipulse_db_max_connections",
        'aipulse_db_connections{state="',
        'aipulse_db_pool_connections{state="checked_out"}',
    ]
    missing = [e for e in expected if e not in body]
    assert not missing, missing


async def test_metrics_report_dependencies_down_instead_of_failing(settings, session_factory):
    m.RUNTIME._at = 0.0
    app = _app(settings, session_factory)  # no engine / redis attached
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/metrics")
    assert r.status_code == 200
    assert 'aipulse_dependency_up{name="postgres"} 0.0' in r.text
    assert 'aipulse_dependency_up{name="redis"} 0.0' in r.text


def test_worker_telemetry_records_histogram(monkeypatch):
    fake = FakeSyncRedis()
    monkeypatch.setattr(telemetry, "_redis", fake)
    telemetry.record("t", 3.0)
    telemetry.record("t", 100.0, failed=True)
    telemetry.record("t", None, retried=True)
    s = fake.store
    assert s["t|count"] == 2 and s["t|sum"] == 103.0 and s["t|failures"] == 1 and s["t|retries"] == 1
    assert s["t|le_5"] == 1 and s["t|le_120"] == 2 and "t|last_success" in s
    fams = m._families_from_task_stats({k: str(v) for k, v in s.items()})
    hist = next(f for f in fams if f.name == "aipulse_celery_task_duration_seconds")
    inf = next(x for x in hist.samples if x.labels.get("le") == "+Inf")
    assert inf.value == 2


def test_worker_telemetry_never_raises(monkeypatch):
    class Down:
        def pipeline(self, transaction: bool = False):  # type: ignore[no-untyped-def]
            raise ConnectionError("down")

    monkeypatch.setattr(telemetry, "_redis", Down())
    telemetry.record("t", 1.0)  # must not raise


# ------------------------------------------------------------------ production config guards
@pytest.mark.parametrize(
    "over, msg",
    [
        ({"jwt_secret": "short"}, "JWT_SECRET"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"cors_origins": ["*"]}, "CORS_ORIGINS"),
        ({"cors_origins": ["http://example.com"]}, "CORS_ORIGINS"),
        ({"debug": True}, "DEBUG"),
        ({"expose_reset_token": True}, "EXPOSE_RESET_TOKEN"),
    ],
)
def test_production_settings_are_enforced(over, msg):
    base = {
        "environment": "production",
        "jwt_secret": "x" * 40,
        "cors_origins": ["https://pulse.example.com"],
    }
    with pytest.raises(ValidationError, match=msg):
        Settings(**{**base, **over})
    Settings(**base)  # the safe baseline is accepted


async def test_security_headers(client):
    r = await client.get("/api/v1/categories")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in r.headers  # only in production (behind TLS)
    token = await register_and_login(client, f"{uuid.uuid4().hex[:8]}@example.com")
    assert token


# ------------------------------------------------------------------ admin: system health, usage, AI config
class HealthRedis(FakeAsyncRedis):
    async def ping(self) -> bool:
        return True

    async def info(self, section: str) -> dict:
        return {"used_memory_human": "1.2M"}

    async def get(self, key: str) -> bytes | None:
        return str(datetime.now(UTC).timestamp()).encode()


async def _staff(client, session_factory) -> dict[str, str]:
    from tests.conftest import make_admin

    await register_and_login(client, "ops-admin@example.com")
    await make_admin(session_factory, "ops-admin@example.com")
    r = await client.post("/api/v1/auth/login", json={"email": "ops-admin@example.com", "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_system_health_reports_every_component(client, session_factory):
    h = await _staff(client, session_factory)
    stats = {
        b"aipulse.ingest_source|count": b"2",
        b"aipulse.ingest_source|last_success": str(datetime.now(UTC).timestamp()).encode(),
    }
    client._transport.app.state.redis = HealthRedis(stats)  # type: ignore[attr-defined]
    r = await client.get("/api/v1/admin/system/health", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    checks = {c["name"]: c for c in body["checks"]}
    assert set(checks) == {
        "database",
        "migrations",
        "redis",
        "scheduler",
        "workers",
        "ingestion",
        "ai_provider",
    }
    assert checks["database"]["status"] == "ok" and checks["database"]["data"]["pgvector"]
    assert checks["migrations"]["status"] == "ok"
    assert checks["migrations"]["data"]["current"] == checks["migrations"]["data"]["head"]
    assert checks["redis"]["data"]["queues"] == {"ingestion": 7}
    assert checks["scheduler"]["status"] == "ok" and checks["workers"]["status"] == "ok"
    assert body["status"] in ("ok", "degraded")
    # Redis down -> reported, not a 500
    client._transport.app.state.redis = None  # type: ignore[attr-defined]
    body = (await client.get("/api/v1/admin/system/health", headers=h)).json()
    assert body["status"] == "down" and {c["name"]: c for c in body["checks"]}["redis"]["status"] == "down"
    # regular users are refused
    u = {"Authorization": f"Bearer {await register_and_login(client, 'plain@example.com')}"}
    assert (await client.get("/api/v1/admin/system/health", headers=u)).status_code == 403


async def test_usage_stats_and_ai_config_never_leak_secrets(client, session_factory, settings):
    h = await _staff(client, session_factory)
    async with session_factory() as s:
        now = datetime.now(UTC)
        s.add_all(
            [
                AIUsage(
                    purpose="rag",
                    provider="anthropic",
                    model="m",
                    input_tokens=50,
                    output_tokens=10,
                    cost_usd=0.002,
                    ok=True,
                    created_at=now,
                ),  # fmt: skip
                AIUsage(purpose="rag", provider="anthropic", model="m", ok=False, error="x", created_at=now),
            ]
        )
        await s.commit()
    r = await client.get("/api/v1/admin/usage", headers=h, params={"days": 7})
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["users_total"] == 1 and u["users_by_role"] == {"admin": 1}
    assert len(u["signups_by_day"]) == 8 and sum(d["value"] for d in u["signups_by_day"]) == 1
    assert u["ai_tokens_total"] == 60 and u["ai_by_model"][0]["errors"] == 1
    assert u["ai_by_day"][-1]["calls"] == 2
    assert (await client.get("/api/v1/admin/usage", headers=h, params={"days": 365})).status_code == 422

    client._transport.app.state.settings = settings.model_copy(  # type: ignore[attr-defined]
        update={"openai_api_key": SecretStr("sk-very-secret"), "llm_provider": "openai"}
    )
    r = await client.get("/api/v1/admin/ai/config", headers=h)
    assert r.status_code == 200
    assert r.json()["openai_api_key_set"] is True and r.json()["anthropic_api_key_set"] is False
    assert "sk-very-secret" not in r.text


async def test_bulk_retry_of_failed_jobs_is_audited(client, session_factory):
    from tests.test_ingestion_api import FakeQueue

    h = await _staff(client, session_factory)
    q = FakeQueue()
    client._transport.app.state.task_queue = q  # type: ignore[attr-defined]
    async with session_factory() as s:
        now = datetime.now(UTC)
        srcs = []
        for slug, enabled in (("a", True), ("b", True), ("c", False)):
            src = Source(slug=slug, name=slug, source_type=SourceType.RSS, connector="rss",
                         url=f"https://{slug}.test/f", default_item_type=ItemType.NEWS, enabled=enabled)  # fmt: skip
            s.add(src)
            srcs.append(src)
        await s.flush()
        a, b, c = srcs
        s.add_all(
            [
                CollectionJob(source_id=a.id, status=JobStatus.FAILED, started_at=now - timedelta(hours=2)),
                # b failed, then recovered: nothing to retry
                CollectionJob(source_id=b.id, status=JobStatus.FAILED, started_at=now - timedelta(hours=3)),
                CollectionJob(
                    source_id=b.id, status=JobStatus.SUCCEEDED, started_at=now - timedelta(hours=1)
                ),
                CollectionJob(source_id=c.id, status=JobStatus.FAILED, started_at=now - timedelta(hours=1)),
            ]
        )
        await s.commit()
    r = await client.post("/api/v1/admin/jobs/retry-failed", headers=h)
    assert r.status_code == 202, r.text
    assert r.json()["retried"] == 1 and r.json()["skipped_sources"] == ["c"]
    assert q.sent == [(str(a.id), "retry")]
    logs = (
        await client.get("/api/v1/admin/audit-logs", headers=h, params={"action": "jobs.retry_failed"})
    ).json()
    assert logs["total"] == 1 and logs["items"][0]["details"]["retried"] == 1
