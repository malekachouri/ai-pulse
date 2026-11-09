"""Retrieval: keyword (PostgreSQL FTS), BM25 re-ranking, semantic (pgvector cosine) and hybrid (RRF).

* Keyword: `websearch_to_tsquery` (explicit queries) or an OR-query of extracted terms (questions), ranked by
  `ts_rank_cd` in SQL.
* BM25: PostgreSQL has no native BM25, so the lexical candidate pool (top N by FTS) is re-scored with
  Okapi BM25 (k1=1.5, b=0.75) in Python. IDF is computed over the candidate pool - documented approximation.
* Semantic: query embedding vs `articles.embedding` (HNSW, cosine). Similarity = 1 - distance.
* Hybrid: Reciprocal Rank Fusion of the BM25 and semantic rankings (k=60), so scores on different scales
  never need to be compared directly.
All modes honour metadata filters (type, category, source, severity, date) and hide duplicates.
"""

import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import Embedder
from app.ai.text import tokens
from app.models import Article
from app.repositories.articles import ArticleRepository
from app.schemas.article import ArticleFilters

RRF_K = 60
POOL = 150


@dataclass
class Hit:
    article: Article
    score: float
    scores: dict[str, float] = field(default_factory=dict)


def bm25_scores(query: list[str], docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
    if not docs:
        return []
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n or 1.0
    df = Counter(t for d in docs for t in set(d))
    q = list(dict.fromkeys(query))
    out = []
    for d in docs:
        tf = Counter(d)
        s = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avgdl))
        out.append(s)
    return out


def rrf(rankings: list[list[uuid.UUID]], k: int = RRF_K) -> dict[uuid.UUID, float]:
    fused: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            fused[doc] = fused.get(doc, 0.0) + 1.0 / (k + rank + 1)
    return fused


_LEXEME = re.compile(r"^[a-z0-9][a-z0-9.\-]*$")


def or_tsquery(terms: list[str]) -> str | None:
    """Safe OR tsquery from free text terms (each term passed through to_tsquery's lexer as a quoted word)."""
    clean = [t.replace(".", " ").replace("-", " ") for t in dict.fromkeys(terms) if _LEXEME.match(t)]
    words = [w for t in clean for w in t.split() if len(w) > 1][:24]
    return " | ".join(f"'{w}'" for w in words) or None


def doc_tokens(a: Article) -> list[str]:
    return tokens(
        f"{a.title} {a.title} {a.description or ''} {(a.content or '')[:3000]}"
    )  # title weighted x2


class Retriever:
    def __init__(self, session: AsyncSession, embedder: Embedder | None = None) -> None:
        self.s = session
        self.embedder = embedder
        self.repo = ArticleRepository(session)

    async def lexical(
        self, query: str, filters: ArticleFilters, *, natural: bool, pool: int = POOL
    ) -> list[Hit]:
        terms = tokens(query)
        base, _ = self.repo.filtered(filters.model_copy(update={"q": None}))
        if natural:
            tsq = or_tsquery(terms)
            if not tsq:
                return []
            ts = func.to_tsquery("english", tsq)
        else:
            ts = func.websearch_to_tsquery("english", query)
        stmt = (
            base.add_columns(func.ts_rank_cd(Article.search_vector, ts).label("rank"))
            .where(Article.search_vector.op("@@")(ts))
            .order_by(func.ts_rank_cd(Article.search_vector, ts).desc())
            .limit(pool)
        )
        rows = (await self.s.execute(stmt)).unique().all()
        if not rows:
            return []
        arts = [r[0] for r in rows]
        bm = bm25_scores(terms, [doc_tokens(a) for a in arts])
        hits = [
            Hit(a, s, {"bm25": round(s, 4), "fts": round(float(r[1]), 5)})
            for a, s, r in zip(arts, bm, rows, strict=True)
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    async def semantic(self, query: str, filters: ArticleFilters, *, pool: int = POOL) -> list[Hit]:
        if self.embedder is None:
            return []
        (qvec,), _ = await self.embedder.embed([query])
        base, _ = self.repo.filtered(filters.model_copy(update={"q": None}))
        dist = Article.embedding.cosine_distance(qvec)
        stmt = (
            base.add_columns(dist.label("d")).where(Article.embedding.is_not(None)).order_by(dist).limit(pool)
        )
        rows = (await self.s.execute(stmt)).unique().all()
        return [Hit(r[0], 1 - float(r[1]), {"semantic": round(1 - float(r[1]), 4)}) for r in rows]

    async def hybrid(
        self, query: str, filters: ArticleFilters, *, natural: bool, pool: int = POOL
    ) -> list[Hit]:
        lex = await self.lexical(query, filters, natural=natural, pool=pool)
        sem = await self.semantic(query, filters, pool=pool)
        by_id: dict[uuid.UUID, Hit] = {}
        for h in [*lex, *sem]:
            if h.article.id in by_id:
                by_id[h.article.id].scores.update(h.scores)
            else:
                by_id[h.article.id] = Hit(h.article, 0.0, dict(h.scores))
        fused = rrf([[h.article.id for h in lex], [h.article.id for h in sem]])
        for doc_id, s in fused.items():
            by_id[doc_id].score = s
            by_id[doc_id].scores["rrf"] = round(s, 5)
        return sorted(by_id.values(), key=lambda h: h.score, reverse=True)


def explain(hit: Hit) -> dict[str, Any]:
    return {k: v for k, v in hit.scores.items()}
