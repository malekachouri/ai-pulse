"""Generic RSS/Atom connector for official vendor blogs and announcement feeds.

Uses conditional GET (ETag / Last-Modified) so unchanged feeds cost one cheap 304.
"""

from typing import Any

import feedparser
from pydantic import Field

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.normalized import NormalizedItem
from app.ingestion.text import html_to_text, struct_to_dt, truncate
from app.models.enums import ItemType


class RssConfig(ConnectorConfig):
    item_type: ItemType = ItemType.NEWS
    include_content: bool = Field(True, description="Store the feed's full text when it provides one")


class RssConnector(Connector):
    key = "rss"
    description = "RSS 2.0 / Atom feed (official blogs, release notes, announcements)"
    Config = RssConfig
    config: RssConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        headers = {}
        if checkpoint.get("etag"):
            headers["If-None-Match"] = checkpoint["etag"]
        if checkpoint.get("last_modified"):
            headers["If-Modified-Since"] = checkpoint["last_modified"]
        resp = await self.http.get(
            self.source.url, headers=headers, rate_limit=self.rate_limit, allow_not_modified=True
        )
        if resp.status_code == 304:
            return FetchResult([], checkpoint=checkpoint, not_modified=True)
        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError(f"Unparseable feed: {parsed.get('bozo_exception')}")
        new_cp = {
            k: v
            for k, v in {
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
            }.items()
            if v
        }
        lang = (parsed.feed.get("language") or "")[:8] or None
        # Newest first regardless of feed order, so the per-run cap keeps the most recent entries.
        entries = sorted(
            parsed.entries,
            key=lambda e: e.get("published_parsed") or e.get("updated_parsed") or (0,),
            reverse=True,
        )
        return FetchResult([(e, lang) for e in entries], checkpoint=new_cp)

    def normalize(self, record: Any) -> list[NormalizedItem]:
        entry, lang = record
        link = entry.get("link") or ""
        external_id = entry.get("id") or entry.get("guid") or link
        content = None
        if self.config.include_content and entry.get("content"):
            content = html_to_text(entry["content"][0].get("value"))
        summary = html_to_text(entry.get("summary"))
        tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")][:15]
        return [
            NormalizedItem(
                external_id=external_id[:512],
                item_type=self.config.item_type,
                title=html_to_text(entry.get("title")) or "",
                url=link,
                description=truncate(summary, 2000),
                content=content if content and content != summary else None,
                author=entry.get("author"),
                language=lang,
                published_at=struct_to_dt(entry.get("published_parsed") or entry.get("updated_parsed")),
                source_updated_at=struct_to_dt(entry.get("updated_parsed")),
                tags=[t.lower()[:64] for t in tags],
                verification=self.config.verification,
                raw={"feed_entry_id": external_id},
            )
        ]
