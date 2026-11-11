"""Shared HTTP plumbing for providers: timeouts, retries on 429/5xx, error mapping (keys never logged)."""

from typing import Any

import httpx

from app.ai.providers.base import ProviderError
from app.ingestion.http import FetchError, HttpClient, RateLimit

_LIMIT = RateLimit(600, 60)


async def post_json(
    http: HttpClient, url: str, payload: dict[str, Any], headers: dict[str, str], provider: str
) -> dict[str, Any]:
    try:
        resp = await http.post(url, json=payload, headers=headers, rate_limit=_LIMIT)
    except FetchError as exc:
        retryable = exc.status is None or exc.status == 429 or exc.status >= 500
        detail = f" - {exc.body}" if exc.body else ""  # e.g. "model not found"; keys are never echoed
        raise ProviderError(
            f"{provider} request failed: {exc}{detail}", retryable=retryable, status=exc.status
        ) from exc
    try:
        data = resp.json()
    except ValueError as exc:
        raise ProviderError(f"{provider} returned non-JSON response", retryable=True) from exc
    if not isinstance(data, dict):
        raise ProviderError(f"{provider} returned an unexpected payload", retryable=False)
    return data


def make_client(timeout: float) -> HttpClient:
    return HttpClient(
        httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0)), max_attempts=3, backoff_base=2.0
    )
