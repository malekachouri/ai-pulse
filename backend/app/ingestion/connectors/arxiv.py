"""arXiv API (Atom). Newest submissions first, paginated with `start`, stopping at the checkpoint.

arXiv terms: at most one request every 3 seconds (enforced by the HTTP client's per-host limit).
"""

import re
from datetime import datetime
from typing import Any

import feedparser
from pydantic import Field

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.normalized import NormalizedItem, PaperPayload
from app.ingestion.text import html_to_text, parse_dt, struct_to_dt, truncate
from app.models.enums import ItemType

ID_RE = re.compile(r"arxiv\.org/abs/([^v\s]+?)(v\d+)?$")


class ArxivConfig(ConnectorConfig):
    query: str = Field("cat:cs.CL OR cat:cs.LG OR cat:cs.AI", max_length=500)
    page_size: int = Field(100, ge=1, le=500)
    max_pages: int = Field(3, ge=1, le=20)


class ArxivConnector(Connector):
    key = "arxiv"
    description = "arXiv API search (newest submissions)"
    Config = ArxivConfig
    config: ArxivConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        since = parse_dt(checkpoint.get("last_published"))
        entries: list[Any] = []
        newest: datetime | None = None
        for page in range(self.config.max_pages):
            resp = await self.http.get(
                self.source.url,
                params={
                    "search_query": self.config.query,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "start": page * self.config.page_size,
                    "max_results": self.config.page_size,
                },
                rate_limit=self.rate_limit,
            )
            batch = feedparser.parse(resp.content).entries
            reached_checkpoint = False
            for e in batch:
                published = struct_to_dt(e.get("published_parsed"))
                if published and newest is None:
                    newest = published
                if since and published and published <= since:
                    reached_checkpoint = True
                    break
                entries.append(e)
            if reached_checkpoint or len(batch) < self.config.page_size:
                break
        cp = {"last_published": (newest or since).isoformat()} if (newest or since) else {}
        return FetchResult(entries, checkpoint=cp)

    def normalize(self, record: Any) -> list[NormalizedItem]:
        e = record
        m = ID_RE.search(e.get("id", ""))
        if not m:
            raise ValueError(f"unexpected arXiv id {e.get('id')!r}")
        arxiv_id = m.group(1)
        title = re.sub(r"\s+", " ", html_to_text(e.get("title")) or "")
        abstract = re.sub(r"\s+", " ", html_to_text(e.get("summary")) or "") or None
        authors = [a.get("name") for a in e.get("authors", []) if a.get("name")]
        pdf = next(
            (link.get("href") for link in e.get("links", []) if link.get("type") == "application/pdf"), None
        )
        primary = (e.get("arxiv_primary_category") or {}).get("term")
        published = struct_to_dt(e.get("published_parsed"))
        url = f"https://arxiv.org/abs/{arxiv_id}"
        return [
            NormalizedItem(
                external_id=arxiv_id,
                item_type=ItemType.RESEARCH,
                title=title,
                url=url,
                description=truncate(abstract, 2000),
                content=abstract,
                author=", ".join(authors[:10]) or None,
                published_at=published,
                source_updated_at=struct_to_dt(e.get("updated_parsed")),
                categories=["ai-research"],
                verification=self.config.verification,
                canonical_key=f"arxiv:{arxiv_id}",
                # arXiv subject codes (cs.CL…) live on the paper, not in free-form tags used for trends
                raw={"arxiv_categories": [t.get("term") for t in e.get("tags", []) if t.get("term")][:10]},
                paper=PaperPayload(
                    arxiv_id=arxiv_id,
                    doi=e.get("arxiv_doi"),
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    primary_category=primary,
                    pdf_url=pdf,
                    published_at=published,
                ),
            )
        ]
