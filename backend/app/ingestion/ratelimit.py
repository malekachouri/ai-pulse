"""Per-host rate limiting. Redis-backed in workers (shared across processes), in-memory for tests/CLI."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

Sleep = Callable[[float], Awaitable[None]]


class RateLimiter(Protocol):
    async def acquire(self, key: str, limit: int, period: float) -> None: ...


class InMemoryRateLimiter:
    """Sliding-log limiter: at most `limit` acquisitions per `period` seconds per key."""

    def __init__(self, sleep: Sleep = asyncio.sleep, clock: Callable[[], float] = time.monotonic) -> None:
        self._log: dict[str, list[float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._sleep = sleep
        self._clock = clock
        self.waited: float = 0.0  # total seconds spent waiting (observability/tests)

    async def acquire(self, key: str, limit: int, period: float) -> None:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            while True:
                now = self._clock()
                log = [t for t in self._log.get(key, []) if now - t < period]
                if len(log) < limit:
                    log.append(now)
                    self._log[key] = log
                    return
                wait = period - (now - log[0]) + 0.01
                self.waited += wait
                self._log[key] = log
                await self._sleep(wait)


class RedisRateLimiter:
    """Fixed-window counter in Redis so every Celery worker shares the same budget per host."""

    def __init__(self, redis_url: str, sleep: Sleep = asyncio.sleep) -> None:
        from redis.asyncio import Redis

        self._redis = Redis.from_url(redis_url)
        self._sleep = sleep

    async def acquire(self, key: str, limit: int, period: float) -> None:
        while True:
            now = time.time()
            window = int(now // period)
            rkey = f"aipulse:rl:{key}:{window}"
            count = await self._redis.incr(rkey)
            if count == 1:
                await self._redis.expire(rkey, int(period) + 1)
            if count <= limit:
                return
            await self._sleep((window + 1) * period - now + 0.05)

    async def close(self) -> None:
        await self._redis.aclose()
