"""AI Comparison: models side by side, using only numbers and facts that collected sources state.

* Benchmarks are the scores quoted by a model's own collected release items ("MMLU 85.2", "90.1% on
  HumanEval"), extracted by the same rules as change detection (app/ai/changes.py). For each benchmark the
  newest release that reports it is used, and the cell carries the quote, the source link and its date.
* Facts (latest version, release date, context window, license, open weights) come from the release records
  and their sources, each with the URL it was read from.
* A benchmark a model's sources do not report is null ("not reported"): nothing is estimated, and
  benchmarks are never mixed across models' unrelated sources. No number is shown without a source.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.changes import BENCHMARKS, extract_benchmarks, extract_license
from app.ai.pipeline import _article_text
from app.core.errors import AppError, NotFoundError
from app.models import AIModel, Article
from app.schemas.comparison import (
    BenchmarkCell,
    BenchmarkRow,
    ComparedModel,
    ComparisonOut,
    SourcedFact,
)

MIN_MODELS, MAX_MODELS = 2, 4
RELEASES_PER_MODEL = 10


def _iso(d: Any) -> str | None:
    return d.isoformat() if d else None


class ComparisonService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def _one(self, m: AIModel) -> tuple[ComparedModel, dict[str, BenchmarkCell]]:
        releases = sorted(
            m.releases,
            key=lambda r: (r.released_at is not None, r.released_at or r.created_at),
            reverse=True,
        )[:RELEASES_PER_MODEL]
        arts = {
            a.id: a
            for a in (
                await self.s.scalars(
                    select(Article).where(Article.id.in_([r.article_id for r in releases if r.article_id]))
                )
            ).unique()
        }
        bench: dict[str, BenchmarkCell] = {}
        context: SourcedFact | None = None
        license_: SourcedFact | None = None
        for r in releases:  # newest first: the first source that states something wins
            a = arts.get(r.article_id) if r.article_id else None
            url = a.url if a else r.source_url
            title = a.title if a else f"{m.name} {r.version or ''}".strip()
            source = a.source.name if a else m.provider
            date = r.released_at or (a.published_at if a else None)
            text = "\n".join(filter(None, [_article_text(a) if a else None, r.notes]))
            for name, hit in extract_benchmarks(text).items():
                bench.setdefault(
                    name,
                    BenchmarkCell(value=hit["value"], quote=hit["quote"], version=r.version, source_url=url,
                                  source_title=title, source=source, date=_iso(date)),
                )  # fmt: skip
            if context is None and r.context_window:
                context = SourcedFact(value=f"{r.context_window:,} tokens", source_url=r.source_url,
                                      date=_iso(r.released_at), basis="release record")  # fmt: skip
            if license_ is None:
                meta = (a.raw or {}).get("license") if a is not None and isinstance(a.raw, dict) else None
                lic, basis = extract_license(text, meta)
                if lic:
                    license_ = SourcedFact(value=lic, source_url=url, date=_iso(date), basis=basis)
        latest = releases[0] if releases else None
        model = ComparedModel(
            id=str(m.id),
            name=m.name,
            provider=m.provider,
            family=m.family,
            homepage_url=m.homepage_url,
            is_open_weights=m.is_open_weights,
            latest_release=(
                SourcedFact(
                    value=latest.version or "release",
                    source_url=latest.source_url,
                    date=_iso(latest.released_at),
                    basis="release record",
                )
                if latest
                else None
            ),  # fmt: skip
            context_window=context,
            license=license_,
            releases_considered=len(releases),
            benchmarks_reported=len(bench),
        )
        return model, bench

    async def compare(self, ids: list[uuid.UUID]) -> ComparisonOut:
        ids = list(dict.fromkeys(ids))
        if not MIN_MODELS <= len(ids) <= MAX_MODELS:
            raise AppError(f"Choose between {MIN_MODELS} and {MAX_MODELS} different models to compare")
        rows = {
            m.id: m
            for m in (
                await self.s.scalars(
                    select(AIModel).where(AIModel.id.in_(ids)).options(selectinload(AIModel.releases))
                )
            ).unique()
        }
        missing = [str(i) for i in ids if i not in rows]
        if missing:
            raise NotFoundError(f"Unknown model: {', '.join(missing)}")
        models: list[ComparedModel] = []
        cells: dict[str, dict[str, BenchmarkCell]] = {}
        for i in ids:  # keep the order the user picked
            model, bench = await self._one(rows[i])
            models.append(model)
            cells[model.id] = bench
        names = [b for b in BENCHMARKS if any(b in c for c in cells.values())]
        names.sort(key=lambda b: -sum(b in c for c in cells.values()))  # stable: catalog order on ties
        benchmarks = [
            BenchmarkRow(
                name=b,
                reported_by=sum(b in c for c in cells.values()),
                cells={mid: c.get(b) for mid, c in cells.items()},
            )
            for b in names
        ]
        note = None
        if not benchmarks:
            note = "None of the collected sources for these models quote benchmark scores."
        elif any(r.reported_by < len(models) for r in benchmarks):
            note = "Empty cells: that model's collected sources do not report the benchmark (not estimated)."
        return ComparisonOut(models=models, benchmarks=benchmarks, note=note)
