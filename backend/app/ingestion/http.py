"""Polite HTTP client for connectors: identification, timeouts, rate limits, retries and backoff."""

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger
from app.ingestion.ratelimit import InMemoryRateLimiter, RateLimiter, Sleep

log = get_logger(__name__)

USER_AGENT = "AIPulse/0.4 (+https://github.com/malekachouri/ai-pulse; technology intelligence aggregator)"
RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class RateLimit:
    limit: int
    period: float  # seconds


# Defaults follow each provider's published guidance; sources can override via config["rate_limit"].
DEFAULT_LIMITS: dict[str, RateLimit] = {
    "services.nvd.nist.gov": RateLimit(5, 30),  # NVD without API key: 5 requests / 30 s
    "export.arxiv.org": RateLimit(1, 3),  # arXiv API terms: no more than 1 request every 3 seconds
    "api.github.com": RateLimit(30, 60),
}
FALLBACK_LIMIT = RateLimit(30, 60)


class FetchError(Exception):
    """A request that failed after all retries (or with a non-retryable status)."""

    def __init__(
        self, message: str, status: int | None = None, url: str | None = None, body: str | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.url = url
        self.body = body  # start of the error response (APIs explain 4xx there); never request data


def _error_body(resp: httpx.Response) -> str | None:
    text = resp.text.strip()
    return " ".join(text.split())[:300] or None


def ratelimit_reset(resp: httpx.Response) -> datetime | None:
    """When a provider says the quota is spent (GitHub-style x-ratelimit-* headers), when it resets."""
    if resp.headers.get("x-ratelimit-remaining") != "0":
        return None
    reset = resp.headers.get("x-ratelimit-reset", "")
    return datetime.fromtimestamp(int(reset), UTC) if reset.isdigit() else datetime.now(UTC)


def retry_after_seconds(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    now = now or datetime.now(UTC)
    return max(0.0, (when - now).total_seconds())


class HttpClient:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        limiter: RateLimiter | None = None,
        *,
        max_attempts: int = 4,
        backoff_base: float = 1.0,
        backoff_cap: float = 60.0,
        sleep: Sleep = asyncio.sleep,
        limits: dict[str, RateLimit] | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._owns_client = client is None
        self.limiter = limiter or InMemoryRateLimiter(sleep=sleep)
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self._sleep = sleep
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self.requests = 0
        self._exhausted: dict[str, datetime] = {}  # host -> quota reset time; no requests until then

    def backoff(self, attempt: int) -> float:
        """Exponential backoff with full jitter: random(0, min(cap, base * 2^attempt))."""
        return random.uniform(0, min(self.backoff_cap, self.backoff_base * (2**attempt)))  # noqa: S311

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        rate_limit: RateLimit | None = None,
        allow_not_modified: bool = False,
    ) -> httpx.Response:
        return await self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            rate_limit=rate_limit,
            allow_not_modified=allow_not_modified,
        )

    async def post(
        self,
        url: str,
        *,
        json: Any,
        headers: dict[str, str] | None = None,
        rate_limit: RateLimit | None = None,
    ) -> httpx.Response:
        return await self.request("POST", url, json=json, headers=headers, rate_limit=rate_limit)

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        rate_limit: RateLimit | None = None,
        allow_not_modified: bool = False,
    ) -> httpx.Response:
        host = urlparse(url).hostname or url
        rl = rate_limit or self.limits.get(host, FALLBACK_LIMIT)
        last_error: str = ""
        status: int | None = None
        for attempt in range(self.max_attempts):
            reset = self._exhausted.get(host)
            if reset is not None and reset > datetime.now(UTC):
                # Providers ask clients not to keep calling once the quota is spent (GitHub bans abusers).
                raise FetchError(
                    f"rate limit of {host} exhausted until {reset.isoformat(timespec='seconds')}",
                    status=429,
                    url=url,
                )
            await self.limiter.acquire(host, rl.limit, rl.period)
            self.requests += 1
            try:
                hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
                resp = await self._client.request(method, url, params=params, json=json, headers=hdrs)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error, status = f"{type(exc).__name__}: {exc}", None
                wait = self.backoff(attempt)
            else:
                if (reset := ratelimit_reset(resp)) is not None:
                    self._exhausted[host] = reset
                if resp.status_code < 300 or (allow_not_modified and resp.status_code == 304):
                    return resp
                status = resp.status_code
                last_error = f"HTTP {resp.status_code}"
                if reset is not None and status in (403, 429):  # primary quota spent: wait for the reset
                    raise FetchError(
                        f"{last_error} from {host}: rate limit exhausted until "
                        f"{reset.isoformat(timespec='seconds')}",
                        status=status,
                        url=url,
                    )
                # GitHub signals secondary rate limits as 403 + Retry-After: retry after the delay asked for.
                secondary = status == 403 and resp.headers.get("Retry-After") is not None
                if resp.status_code not in RETRY_STATUSES and not secondary:
                    raise FetchError(
                        f"{last_error} from {host}", status=status, url=url, body=_error_body(resp)
                    )
                wait = retry_after_seconds(resp.headers.get("Retry-After")) or self.backoff(attempt)
                wait = min(wait, 300.0)
            if attempt + 1 < self.max_attempts:
                log.warning(
                    "http_retry", host=host, attempt=attempt + 1, error=last_error, wait=round(wait, 2)
                )
                await self._sleep(wait)
        raise FetchError(
            f"{last_error} from {host} after {self.max_attempts} attempts", status=status, url=url
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
