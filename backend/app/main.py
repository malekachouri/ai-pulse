import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import health
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.metrics import MetricsMiddleware, metrics_response
from app.core.ratelimit import RateLimitedError, RedisLimiter, check, client_ip
from app.db.session import create_engine, create_session_factory

log = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        if getattr(app.state, "redis", None) is None:
            from redis.asyncio import Redis

            app.state.redis = Redis.from_url(settings.redis_url, socket_timeout=2, socket_connect_timeout=2)
        if getattr(app.state, "rate_limiter", None) is None:
            app.state.rate_limiter = RedisLimiter(app.state.redis)
        if getattr(app.state, "ai_providers", None) is None:
            from app.ai.providers import build_providers

            app.state.ai_providers = build_providers(settings)
            for problem in app.state.ai_providers.problems:
                log.warning("ai_provider_config", problem=problem)
        log.info("startup", environment=settings.environment)
        yield
        await app.state.ai_providers.aclose()
        await app.state.redis.aclose()
        await engine.dispose()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description=(
            "AI & Technology Intelligence Platform. Every item links to its original source; "
            "AI-generated analysis is always returned separately from source content."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )
    app.state.settings = settings

    app.add_middleware(MetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def global_rate_limit(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path.startswith(settings.api_v1_prefix) and request.method != "OPTIONS":
            try:
                await check(request, None, "global", client_ip(request))
            except RateLimitedError as exc:
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
                    headers={"Retry-After": str(exc.retry_after)},
                )
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith(settings.api_v1_prefix):
            response.headers.setdefault("Cache-Control", "no-store")  # API responses may be personal
        if settings.environment == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        if settings.metrics_token is not None:
            expected = f"Bearer {settings.metrics_token.get_secret_value()}"
            if not hmac.compare_digest(request.headers.get("authorization", ""), expected):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "unauthorized",
                            "message": "Metrics token required",
                            "details": None,
                        }
                    },
                )
        return await metrics_response(request.app)

    return app


app = create_app()
