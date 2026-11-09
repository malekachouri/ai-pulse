"""Mocked-HTTP harness for connector tests. Fixtures in tests/fixtures/ingestion are trimmed copies of real
responses captured from each official endpoint on 2026-11-09; synthetic payloads are built inline."""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from app.ingestion.http import HttpClient
from app.ingestion.ratelimit import InMemoryRateLimiter
from app.ingestion.runner import run_source
from app.models import Source

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion"
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_json(name: str) -> Any:
    return json.loads(fixture_bytes(name))


Handler = Callable[[httpx.Request], httpx.Response]


class MockHttp:
    """Routes requests by URL prefix (longest match). Records every request and every sleep."""

    def __init__(self, routes: dict[str, Handler | httpx.Response | list[httpx.Response]]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        for prefix in sorted(self.routes, key=len, reverse=True):
            if url.startswith(prefix):
                r = self.routes[prefix]
                if isinstance(r, list):
                    return r.pop(0) if len(r) > 1 else r[0]
                return r(request) if callable(r) else r
        return httpx.Response(404, text=f"no mock for {url}")

    async def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def client(self, **kw: Any) -> HttpClient:
        transport = httpx.MockTransport(self._handle)
        return HttpClient(
            httpx.AsyncClient(transport=transport),
            InMemoryRateLimiter(sleep=self._sleep),
            sleep=self._sleep,
            backoff_base=0.01,
            **kw,
        )


def xml(body: bytes | str, status: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, content=body.encode() if isinstance(body, str) else body,
                          headers={"Content-Type": "application/xml", **(headers or {})})  # fmt: skip


def js(data: Any, status: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, json=data, headers=headers or {})


async def make_source(session_factory: Any, connector: str, url: str, **kw: Any) -> uuid.UUID:
    async with session_factory() as s:
        src = Source(
            slug=kw.pop("slug", f"{connector.replace('_', '-')}-{uuid.uuid4().hex[:6]}"),
            name=kw.pop("name", f"Test {connector}"),
            source_type=kw.pop("source_type", "api"),
            connector=connector,
            url=url,
            default_item_type=kw.pop("default_item_type", "news"),
            is_official=True,
            reliability=0.9,
            config=kw.pop("config", {}),
            **kw,
        )
        s.add(src)
        await s.commit()
        return src.id


async def ingest(session_factory: Any, source_id: uuid.UUID, mock: MockHttp, now: datetime = NOW, **kw: Any):  # type: ignore[no-untyped-def]
    settings = kw.pop("settings", None) or Settings(environment="test", jwt_secret="x" * 40)
    return await run_source(
        session_factory,
        source_id,
        settings,
        mock.client(),
        now=now,
        trigger=kw.pop("trigger", "manual"),
        **kw,
    )
