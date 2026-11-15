"""A slow AI provider must not get the database connection closed under the work in progress."""

import asyncio

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.ai.pipeline import AnalysisPipeline
from app.db.session import allow_slow_external_calls
from app.models import Article
from tests import feature_data as fd
from tests.ai_fakes import providers


async def _idle(s, guarded: bool) -> None:  # type: ignore[no-untyped-def]
    # PostgreSQL's guard against stuck transactions, shortened from 5 minutes to 1 second for the test.
    await s.execute(text("SET idle_in_transaction_session_timeout = '1s'"))
    await s.execute(select(1))  # a transaction is now open
    if guarded:
        await allow_slow_external_calls(s)
    await asyncio.sleep(2)  # a slow model answering
    await s.execute(select(1))


async def test_a_long_wait_on_the_model_keeps_the_connection(session_factory):
    async with session_factory() as s:
        await _idle(s, guarded=True)
        assert (await s.scalar(text("SHOW idle_in_transaction_session_timeout"))) == "30min"
        await s.commit()
        # SET LOCAL: the raised limit ends with the transaction; it never leaks to the next one.
        assert (await s.scalar(text("SHOW idle_in_transaction_session_timeout"))) != "30min"

    async with session_factory() as s:
        with pytest.raises(DBAPIError):  # without it, PostgreSQL closes the connection mid-work
            await _idle(s, guarded=False)


async def test_reanalysing_chosen_items_does_not_take_on_the_embedding_backlog(session_factory):
    async with session_factory() as s:
        src = await fd.source(s, "embed-scope")
        chosen = await fd.article(s, src, "chosen", title="Chosen item")
        for i in range(3):
            await fd.article(s, src, f"backlog-{i}", title=f"Backlog item {i}")
        await s.commit()
    async with session_factory() as s:
        stats = await AnalysisPipeline(s, providers(embed=True)).run(article_ids=[chosen.id])
        await s.commit()
        missing = (await s.scalars(select(Article.external_id).where(Article.embedding.is_(None)))).all()
    assert stats.embedded == 1
    assert sorted(missing) == ["backlog-0", "backlog-1", "backlog-2"]  # left to the background run
