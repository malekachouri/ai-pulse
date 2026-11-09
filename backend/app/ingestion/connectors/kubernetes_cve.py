"""Official Kubernetes CVE feed (JSON Feed): kubernetes.io/docs/reference/issues-security/official-cve-feed/.

CVSS comes only from the Security Response Committee's own "CVSS Rating: **x.y** (LEVEL)" line.
"""

import re
from typing import Any

from app.ingestion.base import Connector, FetchResult
from app.ingestion.normalized import NormalizedItem, VulnerabilityPayload
from app.ingestion.text import parse_dt, truncate
from app.models.enums import ItemType, Severity

CVSS_RE = re.compile(r"CVSS Rating:\s*\**\s*([\d.]+)\s*\**\s*\((\w+)\)\s*\[?(CVSS:[\d.]+/[A-Z:/]+)?", re.I)
SEV = {"CRITICAL": Severity.CRITICAL, "HIGH": Severity.HIGH, "MEDIUM": Severity.MEDIUM, "LOW": Severity.LOW}


class KubernetesCveConnector(Connector):
    key = "kubernetes_cve_feed"
    description = "Official Kubernetes CVE feed (Security Response Committee)"

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        resp = await self.http.get(self.source.url, rate_limit=self.rate_limit)
        return FetchResult(resp.json().get("items", []))

    def normalize(self, record: Any) -> list[NormalizedItem]:
        i = record
        cve = i["id"]
        text = i.get("content_text") or ""
        score = version = vector = basis = None
        severity = None
        m = CVSS_RE.search(text)
        if m:
            score = float(m.group(1))
            severity = SEV.get(m.group(2).upper())
            vector = m.group(3)
            version = vector.split("/")[0].split(":")[1] if vector else None
            basis = f"Kubernetes SRC CVSS{(' v' + version) if version else ''} {score}" if severity else None
        body = re.sub(r"^CVSS Rating:.*$", "", text, count=1, flags=re.M).strip()
        published = parse_dt(i.get("date_published"))
        fixed = (i.get("status") or "").lower() == "fixed"
        payload = VulnerabilityPayload(
            cve_id=cve,
            description=truncate(body, 4000),
            cvss_score=score,
            cvss_version=version,
            cvss_vector=vector,
            severity=severity,
            affected_products=[{"vendor": "kubernetes", "product": "kubernetes"}],
            patch_available=True if fixed else None,
            published_at=published,
            references=[
                {"url": u, "source": "kubernetes.io", "tags": ["Vendor Advisory"]}
                for u in (i.get("url"), i.get("external_url"))
                if u
            ],
        )
        return [
            NormalizedItem(
                external_id=cve,
                item_type=ItemType.VULNERABILITY,
                title=f"{cve}: {i.get('summary') or 'Kubernetes security issue'}",
                url=i.get("url") or f"https://www.cve.org/cverecord?id={cve}",
                description=truncate(body, 2000),
                content=text,
                published_at=published,
                severity=severity,
                severity_basis=basis,
                categories=["cybersecurity", "kubernetes"],
                tags=["vendor-advisory", *(["fixed"] if fixed else [])],
                verification=self.config.verification,
                canonical_key=f"cve:{cve}",
                raw={
                    "status": i.get("status"),
                    "issue_number": (i.get("_kubernetes_io") or {}).get("issue_number"),
                },
                vulnerability=payload,
            )
        ]
