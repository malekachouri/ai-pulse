"""Only one analysis run at a time, and a failing release comparison never breaks the run."""

from sqlalchemy import select

from app.ai import changes
from app.ai.pipeline import AnalysisPipeline
from app.models import AIAnalysis
from app.models.enums import AnalysisKind, ItemType
from tests import feature_data as fd
from tests.ai_fakes import providers


async def _item(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        src = await fd.source(s, "conc-src")
        a = await fd.article(s, src, "rel", item_type=ItemType.TOOL, title="acme/tool v2.0",
                             canonical_key="gh-release:acme/tool:v2.0")  # fmt: skip
        await s.commit()
        return a.id


async def test_a_second_run_is_skipped_while_one_is_in_progress(session_factory):
    await _item(session_factory)
    async with session_factory() as first, session_factory() as second:
        stats = await AnalysisPipeline(first, providers()).run()
        assert stats.processed == 1 and not stats.skipped_busy  # holds the lock until it commits

        busy = await AnalysisPipeline(second, providers()).run()
        assert busy.skipped_busy and busy.processed == 0
        await second.rollback()

        await first.commit()  # lock released
        again = await AnalysisPipeline(second, providers()).run()
        assert not again.skipped_busy
        await second.commit()


async def test_a_failing_comparison_is_logged_and_the_run_continues(session_factory, monkeypatch):
    aid = await _item(session_factory)

    async def boom(session, article):  # type: ignore[no-untyped-def]
        raise RuntimeError("comparison failed")

    monkeypatch.setattr(changes, "detect", boom)
    async with session_factory() as s:
        stats = await AnalysisPipeline(s, providers()).run()
        await s.commit()
        kinds = set(await s.scalars(select(AIAnalysis.kind).where(AIAnalysis.article_id == aid)))
    assert stats.processed == 1
    assert AnalysisKind.ENTITIES in kinds and AnalysisKind.CHANGES not in kinds
