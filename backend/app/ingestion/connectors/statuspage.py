"""Atlassian Statuspage public API (used by GitHub, OpenAI, Docker, Anthropic, …).

GET {page}/api/v2/incidents.json returns the 50 most recent incidents with the provider's own status.
"""

from typing import Any

from pydantic import Field

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.normalized import IncidentPayload, NormalizedItem
from app.ingestion.text import parse_dt, truncate
from app.models.enums import IncidentStatus, ItemType, Severity

STATUS = {
    "investigating": IncidentStatus.INVESTIGATING,
    "identified": IncidentStatus.IDENTIFIED,
    "monitoring": IncidentStatus.MONITORING,
    "resolved": IncidentStatus.RESOLVED,
    "postmortem": IncidentStatus.RESOLVED,
}
IMPACT_SEVERITY = {
    "critical": Severity.CRITICAL,
    "major": Severity.HIGH,
    "minor": Severity.MEDIUM,
    "none": Severity.INFO,
    "maintenance": Severity.INFO,
}


class StatuspageConfig(ConnectorConfig):
    provider: str = Field(min_length=2, max_length=100, description="Provider name shown in AI Pulse")


class StatuspageConnector(Connector):
    key = "statuspage"
    description = "Atlassian Statuspage public incidents API"
    Config = StatuspageConfig
    config: StatuspageConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        resp = await self.http.get(self.source.url, rate_limit=self.rate_limit)
        data = resp.json()
        base = (data.get("page") or {}).get("url", "").rstrip("/")
        return FetchResult([(i, base) for i in data.get("incidents", [])])

    def normalize(self, record: Any) -> list[NormalizedItem]:
        inc, base = record
        status = STATUS.get(inc.get("status", ""), IncidentStatus.UNKNOWN)
        impact = inc.get("impact")
        updates = sorted(inc.get("incident_updates") or [], key=lambda u: u.get("created_at") or "")
        services = sorted(
            {c["name"] for u in updates for c in (u.get("affected_components") or []) if c.get("name")}
        )
        url = inc.get("shortlink") or (f"{base}/incidents/{inc['id']}" if base else "")
        latest = updates[-1].get("body") if updates else None
        payload = IncidentPayload(
            provider=self.config.provider,
            external_id=inc["id"],
            title=inc["name"],
            status=status,
            status_page_url=url,
            affected_services=services,
            impact=impact,
            started_at=parse_dt(inc.get("started_at") or inc.get("created_at")),
            resolved_at=parse_dt(inc.get("resolved_at")),
            updates=[
                {"at": u.get("created_at"), "status": u.get("status"), "body": truncate(u.get("body"), 2000)}
                for u in updates
            ],
        )
        severity = IMPACT_SEVERITY.get(impact or "")
        return [
            NormalizedItem(
                external_id=inc["id"],
                item_type=ItemType.INCIDENT,
                title=f"{self.config.provider}: {inc['name']}",
                url=url,
                description=truncate(latest, 2000),
                published_at=payload.started_at,
                source_updated_at=parse_dt(inc.get("updated_at")),
                severity=severity,
                severity_basis=f"{self.config.provider} status page impact: {impact}" if severity else None,
                categories=["infrastructure-failures"],
                verification=self.config.verification,
                canonical_key=f"incident:{self.config.provider.lower()}:{inc['id']}",
                incident=payload,
                raw={"status": inc.get("status"), "impact": impact},
            )
        ]
