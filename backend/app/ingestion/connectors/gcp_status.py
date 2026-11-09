"""Google Cloud Service Health: https://status.cloud.google.com/incidents.json (official JSON feed).

Google publishes begin/end times but not investigating/identified phases. Mapping (documented, not guessed):
`end` present → resolved; no `end` → investigating (ongoing per Google).
"""

from typing import Any

from app.ingestion.base import Connector, FetchResult
from app.ingestion.normalized import IncidentPayload, NormalizedItem
from app.ingestion.text import parse_dt, truncate
from app.models.enums import IncidentStatus, ItemType, Severity

SEVERITY = {"high": Severity.HIGH, "medium": Severity.MEDIUM, "low": Severity.LOW}
BASE = "https://status.cloud.google.com/"


class GcpStatusConnector(Connector):
    key = "gcp_status"
    description = "Google Cloud Service Health incidents JSON"

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        resp = await self.http.get(self.source.url, rate_limit=self.rate_limit)
        incidents = sorted(resp.json(), key=lambda i: i.get("modified") or "", reverse=True)
        return FetchResult(incidents)

    def normalize(self, record: Any) -> list[NormalizedItem]:
        i = record
        resolved = parse_dt(i.get("end"))
        status = IncidentStatus.RESOLVED if resolved else IncidentStatus.INVESTIGATING
        title = i.get("external_desc") or "Google Cloud incident"
        url = BASE + (i.get("uri") or f"incidents/{i['id']}")
        products = [p.get("title") for p in i.get("affected_products") or [] if p.get("title")]
        regions = sorted(
            {
                loc.get("id")
                for loc in (i.get("currently_affected_locations") or [])
                + (i.get("previously_affected_locations") or [])
                if loc.get("id")
            }
        )
        latest = (i.get("most_recent_update") or {}).get("text")
        sev = SEVERITY.get(i.get("severity") or "")
        payload = IncidentPayload(
            provider="Google Cloud",
            external_id=i["id"],
            title=title,
            status=status,
            status_page_url=url,
            affected_services=products,
            regions=regions,
            impact=i.get("status_impact"),
            started_at=parse_dt(i.get("begin")),
            resolved_at=resolved,
            updates=[
                {
                    "at": u.get("when") or u.get("created"),
                    "status": u.get("status"),
                    "body": truncate(u.get("text"), 2000),
                }
                for u in (i.get("updates") or [])[:20]
            ],
        )
        return [
            NormalizedItem(
                external_id=i["id"],
                item_type=ItemType.INCIDENT,
                title=f"Google Cloud: {title}",
                url=url,
                description=truncate(latest, 2000),
                published_at=payload.started_at,
                source_updated_at=parse_dt(i.get("modified")),
                severity=sev,
                severity_basis=f"Google Cloud severity: {i.get('severity')}" if sev else None,
                categories=["cloud", "infrastructure-failures"],
                verification=self.config.verification,
                canonical_key=f"incident:google cloud:{i['id']}",
                incident=payload,
                raw={
                    "status_impact": i.get("status_impact"),
                    "most_recent_status": (i.get("most_recent_update") or {}).get("status"),
                },
            )
        ]
