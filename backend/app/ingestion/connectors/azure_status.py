"""Azure status RSS (https://azure.status.microsoft/en-us/status/feed/).

The feed lists only *current* service issues. Items present → open (investigating). Incidents we saw earlier
that are no longer listed are set to *unknown* - the feed doesn't say they were resolved or when, so we don't
claim it; they simply stop being shown as active.
"""

from typing import Any

import feedparser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.normalized import IncidentPayload, NormalizedItem
from app.ingestion.text import html_to_text, struct_to_dt, truncate
from app.models import Incident
from app.models.enums import IncidentStatus, ItemType
from app.repositories.intel import UNRESOLVED


class AzureStatusConnector(Connector):
    key = "azure_status_rss"
    description = "Azure status RSS (current issues only)"
    Config = ConnectorConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        resp = await self.http.get(self.source.url, rate_limit=self.rate_limit)
        return FetchResult(list(feedparser.parse(resp.content).entries))

    def normalize(self, record: Any) -> list[NormalizedItem]:
        e = record
        ext = (e.get("id") or e.get("link") or e.get("title", ""))[:200]
        title = html_to_text(e.get("title")) or "Azure service issue"
        body = html_to_text(e.get("summary"))
        when = struct_to_dt(e.get("published_parsed"))
        url = e.get("link") or "https://azure.status.microsoft/en-us/status/"
        payload = IncidentPayload(
            provider="Azure",
            external_id=ext,
            title=title,
            status=IncidentStatus.INVESTIGATING,
            status_page_url=url,
            started_at=when,
            updates=[
                {"at": when.isoformat() if when else None, "status": "listed", "body": truncate(body, 2000)}
            ],
        )
        return [
            NormalizedItem(
                external_id=ext,
                item_type=ItemType.INCIDENT,
                title=f"Azure: {title}",
                url=url,
                description=truncate(body, 2000),
                published_at=when,
                categories=["cloud", "infrastructure-failures"],
                verification=self.config.verification,
                canonical_key=f"incident:azure:{ext}",
                incident=payload,
            )
        ]

    async def reconcile(self, session: AsyncSession, items: list[NormalizedItem]) -> None:
        listed = {i.incident.external_id for i in items if i.incident}
        stale = await session.scalars(
            select(Incident).where(Incident.provider == "Azure", Incident.status.in_(UNRESOLVED))
        )
        for inc in stale:
            if inc.external_id not in listed:
                inc.status = IncidentStatus.UNKNOWN
                inc.updates = [
                    *(inc.updates or []),
                    {
                        "at": self.now.isoformat(),
                        "status": "no longer listed",
                        "body": "Removed from the Azure status feed; resolution not stated.",
                    },
                ]
                inc.last_verified_at = self.now
