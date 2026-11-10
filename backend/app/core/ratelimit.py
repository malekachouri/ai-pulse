"""HTTP rate limiting.

Fixed-window counters keyed by scope and client (user id when signed in, otherwise client IP). Redis
is used in deployments so every API replica shares the same counters; an in-memory backend exists for
tests. If Redis is unreachable the limiter *fails open* (requests are allowed, a warning is logged and
`aipulse_dependency_up{name="redis"}` drops), because refusing all traffic would turn a cache outage into
a full outage. Limits are configured with `RATE_LIMIT_*` settings in the form "<count>/<second|minute|hour>".
"""

import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import Depends, Request, Response

from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.metrics import RATE_LIMITED

log = get_logger(__name__)
_PERIODS = {"second": 1, "minute": 60, "hour": 3600}
_SPEC = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour)\s*$")


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message, {"retry_after_seconds": retry_after})
        self.retry_after = retry_after


@dataclass(frozen=True)
class Limit:
    count: int
    period: int

    @classmethod
    def parse(cls, spec: str) -> Limit:
        m = _SPEC.match(spec)
        if not m:
            raise ValueError(f"Invalid rate limit '{spec}': use '<count>/<second|minute|hour>'")
        return cls(int(m.group(1)), _PERIODS[m.group(2)])


class LimiterBackend(Protocol):
    async def hit(self, key: str, period: int) -> int: ...


class InMemoryLimiter:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def hit(self, key: str, period: int) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class RedisLimiter:
    def __init__(self, redis: Any) -> None:
        self.redis = redis

    async def hit(self, key: str, period: int) -> int:
        pipe = self.redis.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, period + 1)
        count, _ = await pipe.execute()
        return int(count)


def client_ip(request: Request) -> str:
    # uvicorn rewrites request.client from X-Forwarded-For only for FORWARDED_ALLOW_IPS (trusted proxies).
    return request.client.host if request.client else "unknown"


async def check(request: Request, response: Response | None, scope: str, ident: str) -> None:
    settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    backend: LimiterBackend | None = getattr(request.app.state, "rate_limiter", None)
    if backend is None:
        return
    limit = Limit.parse(getattr(settings, f"rate_limit_{scope}"))
    window = int(time.time() // limit.period)
    try:
        count = await backend.hit(f"aipulse:rl:{scope}:{ident}:{window}", limit.period)
    except Exception as exc:  # noqa: BLE001 - fail open, see module docstring
        log.warning("rate_limit_backend_unavailable", error=type(exc).__name__)
        return
    remaining = max(0, limit.count - count)
    retry_after = max(1, int(limit.period - time.time() % limit.period))
    if response is not None:
        response.headers["X-RateLimit-Limit"] = str(limit.count)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    if count > limit.count:
        RATE_LIMITED.labels(scope).inc()
        raise RateLimitedError(f"Too many requests; retry in {retry_after} s", retry_after)


def limiter(scope: str, *, per_user: bool = False) -> Any:
    """Route dependency. `per_user` keys signed-in callers by user id (falls back to IP)."""

    async def dep(request: Request, response: Response) -> None:
        ident = client_ip(request)
        if per_user:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                from app.core.security import decode_access_token

                try:
                    ident = f"user:{decode_access_token(request.app.state.settings, auth[7:])['sub']}"
                except Exception:  # noqa: BLE001 - invalid tokens are rejected later by the auth dependency
                    log.debug("rate_limit_token_ignored")
        await check(request, response, scope, ident)

    return Depends(dep)
