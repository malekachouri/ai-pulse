"""CISA Known Exploited Vulnerabilities catalog (official JSON).

Every entry flags its CVE as known-exploited with CISA's required action and due date. Articles are only
created for entries added within `article_window_days`; older entries just update the vulnerability record
(so a first run doesn't flood feeds with ~1,800 historical items). KEV publishes no CVSS: none is invented.
"""

from datetime import timedelta
from typing import Any

from pydantic import Field

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.normalized import NormalizedItem, VulnerabilityPayload
from app.ingestion.text import parse_date, truncate
from app.models.enums import ItemType


class KevConfig(ConnectorConfig):
    article_window_days: int = Field(30, ge=1, le=3650)
    max_items: int = Field(5000, ge=1, le=20000)


class CisaKevConnector(Connector):
    key = "cisa_kev"
    description = "CISA Known Exploited Vulnerabilities catalog"
    Config = KevConfig
    config: KevConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        headers = {"If-None-Match": checkpoint["etag"]} if checkpoint.get("etag") else {}
        resp = await self.http.get(
            self.source.url, headers=headers, rate_limit=self.rate_limit, allow_not_modified=True
        )
        if resp.status_code == 304:
            return FetchResult([], checkpoint=checkpoint, not_modified=True)
        data = resp.json()
        vulns = sorted(data.get("vulnerabilities", []), key=lambda v: v.get("dateAdded") or "", reverse=True)
        cp = {
            "catalog_version": data.get("catalogVersion"),
            **({"etag": resp.headers["ETag"]} if resp.headers.get("ETag") else {}),
        }
        return FetchResult(vulns, checkpoint=cp)

    def normalize(self, record: Any) -> list[NormalizedItem]:
        v = record
        cve = v["cveID"]
        added = parse_date(v.get("dateAdded"))
        notes = [n.strip() for n in (v.get("notes") or "").split(";") if n.strip().startswith("http")]
        payload = VulnerabilityPayload(
            cve_id=cve,
            known_exploited=True,
            kev_date_added=added,
            kev_due_date=parse_date(v.get("dueDate")),
            remediation=f"CISA required action: {v['requiredAction']}" if v.get("requiredAction") else None,
            cwe_ids=v.get("cwes") or None,
            affected_products=[{"vendor": v.get("vendorProject"), "product": v.get("product")}],
            references=[{"url": u, "source": "CISA KEV notes", "tags": []} for u in notes] or None,
        )
        recent = (
            added is not None and added >= (self.now - timedelta(days=self.config.article_window_days)).date()
        )
        published = None
        if added:
            from datetime import UTC, datetime

            published = datetime(added.year, added.month, added.day, tzinfo=UTC)
        ransomware = v.get("knownRansomwareCampaignUse")
        return [
            NormalizedItem(
                external_id=cve,
                item_type=ItemType.VULNERABILITY,
                title=f"{cve} added to CISA KEV: {v.get('vulnerabilityName') or v.get('product')}",
                url=f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={cve}",
                description=truncate(v.get("shortDescription"), 2000),
                content=f"Required action: {v.get('requiredAction')}\nDue date: {v.get('dueDate')}"
                + (f"\nKnown ransomware campaign use: {ransomware}" if ransomware else ""),
                published_at=published,
                categories=["cybersecurity"],
                tags=["known-exploited", "cisa-kev"],
                verification=self.config.verification,
                canonical_key=f"cve:{cve}",
                create_article=recent,
                raw={
                    "vendorProject": v.get("vendorProject"),
                    "product": v.get("product"),
                    "knownRansomwareCampaignUse": ransomware,
                },
                vulnerability=payload,
            )
        ]
