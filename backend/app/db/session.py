from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SLOW_CALL_IDLE_LIMIT = "30min"


async def allow_slow_external_calls(session: AsyncSession) -> None:
    """Let this transaction wait on an AI provider for longer than PostgreSQL's 5-minute
    idle_in_transaction_session_timeout (infra/postgres/postgresql.conf), which otherwise closes the
    connection while a local model on a CPU is still answering. SET LOCAL: this transaction only; the
    server-wide guard against leaked transactions stays in place everywhere else."""
    await session.execute(text(f"SET LOCAL idle_in_transaction_session_timeout = '{SLOW_CALL_IDLE_LIMIT}'"))
