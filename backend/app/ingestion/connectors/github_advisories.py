"""GitHub Security Advisory database - reviewed global advisories (vendor/ecosystem advisories).

GET https://api.github.com/advisories?type=reviewed&sort=updated&direction=desc
Each advisory gives affected packages, vulnerable ranges and the first patched version. Remediation
text is built only from those fields ("upgrade <package> to <first patched version>"); severity and
CVSS come from the
advisory with the basis recorded. Withdrawn advisories are skipped. Advisories without a CVE id are stored as
articles only (the vulnerability table is keyed by CVE).
"""

from typing import Any

from pydantic import Field

from app.ingestion.base import ConnectorConfig, FetchResult
from app.ingestion.connectors.github import API, _GitHub
from app.ingestion.normalized import NormalizedItem, VulnerabilityPayload
from app.ingestion.text import parse_dt, truncate
from app.models.enums import ItemType, Severity

SEV = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "moderate": Severity.MEDIUM,
    "low": Severity.LOW,
}


class AdvisoriesConfig(ConnectorConfig):
    ecosystems: list[str] = Field(default_factory=list, description="e.g. pip, npm, go, maven; empty = all")
    per_page: int = Field(100, ge=1, le=100)
    max_pages: int = Field(3, ge=1, le=20)


def remediation_text(vulns: list[dict[str, Any]], ghsa: str) -> str | None:
    fixes = []
    for v in vulns:
        pkg = (v.get("package") or {}).get("name")
        patched = v.get("first_patched_version")
        if isinstance(patched, dict):  # older API shape
            patched = patched.get("identifier")
        if pkg and patched:
            fixes.append(f"upgrade {pkg} to {patched} or later")
    if not fixes:
        return None
    return f"GitHub Security Advisory {ghsa}: " + "; ".join(dict.fromkeys(fixes)) + "."


class GitHubAdvisoriesConnector(_GitHub):
    key = "github_advisories"
    description = "GitHub reviewed security advisories (packages, vulnerable ranges, patched versions)"
    Config = AdvisoriesConfig
    config: AdvisoriesConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        since = checkpoint.get("updated_at")
        records: list[Any] = []
        newest = since
        ecosystems = self.config.ecosystems or [None]
        for eco in ecosystems:
            params: dict[str, Any] | None = {
                "type": "reviewed",
                "sort": "updated",
                "direction": "desc",
                "per_page": self.config.per_page,
                **({"ecosystem": eco} if eco else {}),
            }
            url: str | None = f"{API}/advisories"
            for _ in range(self.config.max_pages):
                if not url:
                    break
                page, url = await self.get_json(url, params)
                params = None
                stop = False
                for adv in page:
                    updated = adv.get("updated_at") or ""
                    if since and updated <= since:
                        stop = True
                        break
                    newest = max(newest or "", updated)
                    records.append(adv)
                if stop:
                    break
        uniq = {a["ghsa_id"]: a for a in records}
        return FetchResult(list(uniq.values()), checkpoint={"updated_at": newest} if newest else {})

    def normalize(self, record: Any) -> list[NormalizedItem]:
        a = record
        if a.get("withdrawn_at"):
            return []
        ghsa, cve = a["ghsa_id"], a.get("cve_id")
        sev = SEV.get((a.get("severity") or "").lower())
        cvss = (
            (a.get("cvss_severities") or {}).get("cvss_v4")
            or (a.get("cvss_severities") or {}).get("cvss_v3")
            or a.get("cvss")
            or {}
        )
        score = cvss.get("score") or None
        vector = cvss.get("vector_string")
        version = vector.split("/")[0].split(":")[1] if vector and vector.startswith("CVSS:") else None
        basis = (
            f"GitHub Security Advisory severity: {a.get('severity')}" + (f" (CVSS {score})" if score else "")
            if sev
            else None
        )
        vulns = a.get("vulnerabilities") or []
        products = [
            {
                "ecosystem": (v.get("package") or {}).get("ecosystem"),
                "product": (v.get("package") or {}).get("name"),
                "vulnerable_range": v.get("vulnerable_version_range"),
                "patched": v.get("first_patched_version")
                if not isinstance(v.get("first_patched_version"), dict)
                else v["first_patched_version"].get("identifier"),
            }
            for v in vulns
        ]
        refs = [{"url": u, "source": "GitHub Advisory", "tags": []} for u in (a.get("references") or [])][:30]
        payload = None
        if cve:
            payload = VulnerabilityPayload(
                cve_id=cve,
                description=a.get("description") or a.get("summary"),
                cvss_score=score,
                cvss_version=version,
                cvss_vector=vector,
                severity=sev,
                cwe_ids=[c["cwe_id"] for c in a.get("cwes") or [] if c.get("cwe_id")] or None,
                affected_products=products or None,
                patch_available=True if any(p["patched"] for p in products) else None,
                remediation=remediation_text(vulns, ghsa),
                references=[
                    {"url": a["html_url"], "source": "GitHub Advisory", "tags": ["Vendor Advisory"]},
                    *refs,
                ],
                published_at=parse_dt(a.get("published_at")),
            )
        packages = ", ".join(sorted({p["product"] for p in products if p["product"]}))[:200]
        return [
            NormalizedItem(
                external_id=ghsa,
                item_type=ItemType.VULNERABILITY,
                title=f"{cve or ghsa}: {a.get('summary') or 'Security advisory'}"
                + (f" ({packages})" if packages else ""),
                url=a["html_url"],
                description=truncate(a.get("summary"), 500),
                content=a.get("description"),
                published_at=parse_dt(a.get("published_at")),
                source_updated_at=parse_dt(a.get("updated_at")),
                severity=sev,
                severity_basis=basis,
                categories=["cybersecurity"],
                tags=[
                    "vendor-advisory",
                    *sorted({(p["ecosystem"] or "").lower() for p in products if p["ecosystem"]}),
                ][:8],
                verification=self.config.verification,
                canonical_key=f"cve:{cve}" if cve else f"ghsa:{ghsa}",
                raw={"ghsa_id": ghsa},
                vulnerability=payload,
            )
        ]
