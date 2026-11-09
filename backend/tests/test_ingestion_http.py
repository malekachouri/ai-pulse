from datetime import UTC, datetime

import httpx
import pytest

from app.ingestion.http import FetchError, retry_after_seconds
from app.ingestion.ratelimit import InMemoryRateLimiter
from tests.ingestion_helpers import MockHttp


def test_retry_after_parsing():
    assert retry_after_seconds("120") == 120
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    assert retry_after_seconds("Mon, 09 Nov 2026 12:00:30 GMT", now) == 30
    assert retry_after_seconds("garbage") is None and retry_after_seconds(None) is None


async def test_retries_transient_errors_honouring_retry_after():
    mock = MockHttp({"https://api.test/": [
        httpx.Response(503), httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={"ok": 1}),
    ]})  # fmt: skip
    r = await mock.client().get("https://api.test/x")
    assert r.json() == {"ok": 1}
    assert len(mock.requests) == 3
    assert mock.sleeps[1] == 7  # Retry-After wins over computed backoff


async def test_non_retryable_status_fails_fast():
    mock = MockHttp({"https://api.test/": httpx.Response(404)})
    with pytest.raises(FetchError) as e:
        await mock.client().get("https://api.test/x")
    assert e.value.status == 404 and len(mock.requests) == 1


async def test_gives_up_after_max_attempts():
    mock = MockHttp({"https://api.test/": httpx.Response(502)})
    with pytest.raises(FetchError, match="after 3 attempts"):
        await mock.client(max_attempts=3).get("https://api.test/x")
    assert len(mock.requests) == 3 and len(mock.sleeps) == 2


async def test_transport_errors_are_retried():
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, text="ok")

    mock = MockHttp({"https://api.test/": flaky})
    assert (await mock.client().get("https://api.test/x")).text == "ok"


async def test_backoff_is_bounded():
    c = MockHttp({}).client(backoff_cap=5)
    c.backoff_base = 10
    assert all(0 <= c.backoff(a) <= 5 for a in range(10))


async def test_rate_limiter_waits_when_budget_exhausted():
    t = {"now": 0.0}
    waits: list[float] = []

    async def sleep(s: float) -> None:
        waits.append(s)
        t["now"] += s

    rl = InMemoryRateLimiter(sleep=sleep, clock=lambda: t["now"])
    for _ in range(3):
        await rl.acquire("host", 2, 10)
    assert len(waits) == 1 and 9.9 < waits[0] <= 10.1
    await rl.acquire("other-host", 2, 10)  # independent budget
    assert len(waits) == 1


async def test_per_host_default_limits_apply():
    mock = MockHttp({"https://export.arxiv.org/": httpx.Response(200, text="<feed/>")})
    client = mock.client()
    for _ in range(2):
        await client.get("https://export.arxiv.org/api/query")
    # arXiv terms: 1 request per 3 s -> the second call had to wait
    assert mock.sleeps and mock.sleeps[0] > 2.9
