"""Integration test fixtures. Requires PostgreSQL with pgvector (TEST_DATABASE_URL).

The schema is built with the real Alembic migrations, so migrations are tested on every run.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from app.main import create_app
from app.models import Article, Source
from app.models.enums import ItemType, Severity, SourceType, VerificationStatus

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/aipulse_test"
)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Sup3r-Secret-pass!"
SEEDED: dict[str, int] = {}


class CapturingEmail:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def _alembic_config() -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    cfg.attributes["database_url"] = TEST_DB_URL
    return cfg


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        environment="test",
        database_url=TEST_DB_URL,
        jwt_secret="test-secret-key-that-is-long-enough-123456",
        cookie_secure=False,
        log_json=False,
        log_level="WARNING",
        expose_reset_token=False,
        rate_limit_enabled=False,  # covered by tests/test_ops.py with an in-memory backend
    )


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> None:
    async def _reset() -> None:
        engine = create_engine(Settings(database_url=TEST_DB_URL))
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    asyncio.run(_reset())
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")  # migration round-trip
    command.upgrade(cfg, "head")

    async def _count_seeded() -> None:
        engine = create_engine(Settings(database_url=TEST_DB_URL))
        async with engine.connect() as conn:
            SEEDED["sources"] = (await conn.execute(text("SELECT count(*) FROM sources"))).scalar_one()
        await engine.dispose()

    asyncio.run(_count_seeded())


@pytest.fixture(scope="session")
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    yield create_session_factory(engine)
    await engine.dispose()


async def _truncate(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        tables = (
            await s.scalars(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename NOT IN ('roles','categories','alembic_version')"
                )
            )
        ).all()
        await s.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
        await s.commit()


@pytest.fixture(autouse=True)
async def clean_tables(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    await _truncate(session_factory)  # also removes the migration-seeded catalog sources
    yield


@pytest.fixture
def email_sender() -> CapturingEmail:
    return CapturingEmail()


@pytest.fixture
async def client(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession], email_sender: CapturingEmail
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    app.state.session_factory = session_factory
    app.state.email_sender = email_sender
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def register_and_login(client: AsyncClient, email: str = "user@example.com") -> str:
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def make_admin(session_factory: async_sessionmaker[AsyncSession], email: str) -> None:
    async with session_factory() as s:
        await s.execute(
            text("UPDATE users SET role_id=(SELECT id FROM roles WHERE name='admin') WHERE email=:e"),
            {"e": email},
        )
        await s.commit()


@pytest.fixture
async def seeded(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, uuid.UUID]:
    """A small, clearly-synthetic dataset for query tests (test-only, never shipped as content)."""
    async with session_factory() as s:
        src = Source(
            slug="test-feed",
            name="Test Feed",
            source_type=SourceType.RSS,
            connector="rss",
            url="https://example.test/feed.xml",
            default_item_type=ItemType.NEWS,
            is_official=True,
            reliability=0.9,
        )
        s.add(src)
        await s.flush()
        now = datetime.now(UTC)

        def art(ext: str, title: str, **kw: object) -> Article:
            base: dict[str, object] = dict(
                source_id=src.id,
                external_id=ext,
                item_type=ItemType.NEWS,
                title=title,
                url=f"https://example.test/{ext}",
                collected_at=now,
                published_at=now,
                content_hash=ext.ljust(64, "0"),
                verification_status=VerificationStatus.OFFICIAL,
            )
            base.update(kw)
            return Article(**base)

        a1 = art(
            "a1",
            "Retrieval augmented generation benchmark released",
            description="A new RAG evaluation suite",
            tags=["rag", "evaluation"],
            importance_score=80,
        )
        a2 = art("a2", "Kubernetes 1.99 patch release", item_type=ItemType.DEVOPS, importance_score=40)
        a3 = art(
            "a3",
            "CVE-2099-0001 in example library",
            item_type=ItemType.VULNERABILITY,
            severity=Severity.CRITICAL,
            severity_basis="NVD CVSS v3.1 base score 9.8",
            importance_score=95,
        )
        s.add_all([a1, a2, a3])
        await s.flush()
        dup = art("a4", "Retrieval augmented generation benchmark released (mirror)", duplicate_of_id=a1.id)
        s.add(dup)
        await s.commit()
        return {"source": src.id, "a1": a1.id, "a2": a2.id, "a3": a3.id, "dup": dup.id}
