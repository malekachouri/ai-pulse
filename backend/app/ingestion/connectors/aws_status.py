"""AWS Health Dashboard public RSS (https://status.aws.amazon.com/rss/all.rss).

The public feed has no structured status, and it keeps old events listed without a closing entry, so:
* title "Service is operating normally" or containing "[RESOLVED]" → resolved
* any other entry is treated as open **only if its latest update is younger than `max_open_age_hours`**;
  older unresolved-looking entries get status *unknown* (never shown as active).
Each update is a separate item sharing the event guid; the newest one per guid is used.
"""

import re
from datetime import timedelta
from typing import Any

import feedparser
from pydantic import Field

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.normalized import IncidentPayload, NormalizedItem
from app.ingestion.text import html_to_text, struct_to_dt, truncate
from app.models.enums import IncidentStatus, ItemType

REGION_RE = re.compile(r"[a-z]{2}(?:-gov)?-[a-z]+-\d")


class AwsStatusConfig(ConnectorConfig):
    max_open_age_hours: int = Field(24, ge=1, le=168)


class AwsStatusConnector(Connector):
    key = "aws_status_rss"
    description = "AWS Health Dashboard public RSS"
    Config = AwsStatusConfig
    config: AwsStatusConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        resp = await self.http.get(self.source.url, rate_limit=self.rate_limit)
        parsed = feedparser.parse(resp.content)
        latest: dict[str, Any] = {}
        for e in parsed.entries:
            guid = e.get("id") or e.get("link")
            if guid and (
                guid not in latest
                or (e.get("published_parsed") or ()) > (latest[guid].get("published_parsed") or ())
            ):
                latest[guid] = e
        return FetchResult(list(latest.values()))

    def status_for(self, title: str, updated_age: timedelta) -> IncidentStatus:
        if title.lower().startswith("service is operating normally") or "[resolved]" in title.lower():
            return IncidentStatus.RESOLVED
        if updated_age <= timedelta(hours=self.config.max_open_age_hours):
            return IncidentStatus.INVESTIGATING
        return IncidentStatus.UNKNOWN

    def normalize(self, record: Any) -> list[NormalizedItem]:
        e = record
        guid = e.get("id") or e.get("link")
        title = html_to_text(e.get("title")) or "AWS service event"
        when = struct_to_dt(e.get("published_parsed"))
        status = self.status_for(title, self.now - when if when else timedelta.max)
        body = html_to_text(e.get("summary"))
        event_key = guid.split("#", 1)[-1]
        regions = sorted(set(REGION_RE.findall(event_key)))
        service = event_key.split("_", 1)[0]
        if regions:
            service = service.replace(f"-{regions[0]}", "")
        payload = IncidentPayload(
            provider="AWS",
            external_id=event_key,
            title=title,
            status=status,
            status_page_url="https://health.aws.amazon.com/health/status",
            affected_services=[service] if service else [],
            regions=regions,
            started_at=when,
            resolved_at=when if status == IncidentStatus.RESOLVED else None,
            updates=[
                {"at": when.isoformat() if when else None, "status": title, "body": truncate(body, 2000)}
            ],
        )
        return [
            NormalizedItem(
                external_id=event_key[:512],
                item_type=ItemType.INCIDENT,
                title=f"AWS: {title}",
                url=e.get("link") or "https://status.aws.amazon.com/",
                description=truncate(body, 2000),
                published_at=when,
                categories=["cloud", "infrastructure-failures"],
                verification=self.config.verification,
                canonical_key=f"incident:aws:{event_key}",
                incident=payload,
                raw={"guid": guid, "derived_status_rule": "aws_rss_title_and_age"},
            )
        ]
