"""NVD CVE API 2.0 (https://services.nvd.nist.gov/rest/json/cves/2.0).

* Incremental by `lastModStartDate`/`lastModEndDate` windows (NVD allows at most 120 days per window).
* Paginated with `startIndex` / `resultsPerPage`.
* Rate limits per NVD terms: 5 requests / 30 s without a key, 50 / 30 s with NVD_API_KEY (sent as `apiKey`).
* Severity/score: NVD's own ("Primary") score is preferred, else the CNA's ("Secondary"). The basis always
  names the CVSS version, score and scorer. CVEs without CVSS have no severity. Rejected CVEs are skipped.
* NVD has no remediation field: `remediation` is only filled from CISA KEV's required action if embedded.
"""

from datetime import datetime, timedelta
from typing import Any

from pydantic import Field

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.http import RateLimit
from app.ingestion.normalized import NormalizedItem, VulnerabilityPayload
from app.ingestion.text import parse_date, parse_dt, truncate
from app.models.enums import ItemType, Severity

NVD_FMT = "%Y-%m-%dT%H:%M:%S.000"
MAX_WINDOW = timedelta(days=120)
METRIC_ORDER = ["cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]
SEV = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "NONE": Severity.INFO,
}


class NvdConfig(ConnectorConfig):
    initial_days: int = Field(2, ge=1, le=120, description="Look-back for the very first run")
    page_size: int = Field(500, ge=1, le=2000)
    max_pages: int = Field(10, ge=1, le=100)
    max_items: int = Field(5000, ge=1, le=20000)


def _fmt(dt: datetime) -> str:
    return dt.strftime(NVD_FMT) + "Z"


def pick_metric(metrics: dict[str, Any]) -> tuple[dict[str, Any], str, dict[str, Any]] | None:
    """Return (cvssData, version_key, metric) preferring NVD Primary, then the newest CVSS version."""
    candidates = [(k, m) for k in METRIC_ORDER for m in metrics.get(k, [])]
    if not candidates:
        return None
    primary = [c for c in candidates if c[1].get("type") == "Primary"]
    k, m = (primary or candidates)[0]
    return m["cvssData"], k, m


def cpe_products(configurations: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cfg in configurations or []:
        for node in cfg.get("nodes", []):
            for match in node.get("cpeMatch", []):
                if not match.get("vulnerable"):
                    continue
                parts = match.get("criteria", "").split(":")
                if len(parts) < 6:
                    continue
                entry = {"vendor": parts[3], "product": parts[4], "cpe": match["criteria"]}
                version = parts[5]
                if version not in ("*", "-"):
                    entry["version"] = version
                for key in (
                    "versionStartIncluding",
                    "versionStartExcluding",
                    "versionEndIncluding",
                    "versionEndExcluding",
                ):
                    if match.get(key):
                        entry[key] = match[key]
                out.append(entry)
                if len(out) >= limit:
                    return out
    return out


class NvdConnector(Connector):
    key = "nvd"
    description = "NVD CVE API 2.0 (incremental by last-modified date)"
    Config = NvdConfig
    config: NvdConfig

    def _rate(self) -> RateLimit:
        if self.rate_limit:
            return self.rate_limit
        return RateLimit(50, 30) if self.settings.nvd_api_key else RateLimit(5, 30)

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        start = parse_dt(checkpoint.get("last_mod_end")) or (
            self.now - timedelta(days=self.config.initial_days)
        )
        headers = (
            {"apiKey": self.settings.nvd_api_key.get_secret_value()} if self.settings.nvd_api_key else {}
        )
        records: list[Any] = []
        pages = 0
        while start < self.now and pages < self.config.max_pages:
            end = min(start + MAX_WINDOW, self.now)
            index, total = 0, None
            while (total is None or index < total) and pages < self.config.max_pages:
                resp = await self.http.get(
                    self.source.url,
                    params={
                        "lastModStartDate": _fmt(start),
                        "lastModEndDate": _fmt(end),
                        "startIndex": index,
                        "resultsPerPage": self.config.page_size,
                    },
                    headers=headers,
                    rate_limit=self._rate(),
                )
                data = resp.json()
                pages += 1
                total = data.get("totalResults", 0)
                batch = data.get("vulnerabilities", [])
                records.extend(batch)
                index += len(batch)
                if not batch:
                    break
            if total is not None and index < total:
                # page budget exhausted mid-window: resume this window next run (idempotent re-reads are fine)
                return FetchResult(
                    records, checkpoint={"last_mod_end": start.isoformat(), "partial_window": True}
                )
            start = end
        return FetchResult(records, checkpoint={"last_mod_end": start.isoformat()})

    def normalize(self, record: Any) -> list[NormalizedItem]:
        c = record["cve"]
        cve = c["id"]
        if c.get("vulnStatus") == "Rejected":
            return []
        desc = next((d["value"] for d in c.get("descriptions", []) if d.get("lang") == "en"), None)
        picked = pick_metric(c.get("metrics", {}))
        score = version = vector = basis = None
        severity: Severity | None = None
        if picked:
            data, _key, metric = picked
            score, version, vector = data.get("baseScore"), data.get("version"), data.get("vectorString")
            label = data.get("baseSeverity") or metric.get("baseSeverity")
            severity = SEV.get((label or "").upper())
            who = "NVD" if metric.get("type") == "Primary" else f"CNA {metric.get('source')}"
            basis = f"CVSS v{version} base score {score} ({who})" if severity else None
        refs = [
            {"url": r["url"], "source": r.get("source"), "tags": r.get("tags", [])}
            for r in c.get("references", [])
        ]
        cwes = sorted(
            {
                d["value"]
                for w in c.get("weaknesses", [])
                for d in w.get("description", [])
                if d.get("value", "").startswith("CWE-")
            }
        )
        in_kev = bool(c.get("cisaExploitAdd"))
        payload = VulnerabilityPayload(
            cve_id=cve,
            description=desc,
            cvss_score=score,
            cvss_version=version,
            cvss_vector=vector,
            severity=severity,
            cwe_ids=cwes,
            affected_products=cpe_products(c.get("configurations", [])),
            known_exploited=True if in_kev else None,
            kev_date_added=parse_date(c.get("cisaExploitAdd")),
            kev_due_date=parse_date(c.get("cisaActionDue")),
            remediation=f"CISA required action: {c['cisaRequiredAction']}"
            if c.get("cisaRequiredAction")
            else None,
            patch_available=True if any("Patch" in r["tags"] for r in refs) else None,
            references=refs[:100],
            published_at=parse_dt(c.get("published")),
            last_modified_at=parse_dt(c.get("lastModified")),
        )
        return [
            NormalizedItem(
                external_id=cve,
                item_type=ItemType.VULNERABILITY,
                title=f"{cve}: {truncate(desc, 160) or 'No description yet'}",
                url=f"https://nvd.nist.gov/vuln/detail/{cve}",
                description=desc,
                published_at=payload.published_at,
                source_updated_at=payload.last_modified_at,
                severity=severity,
                severity_basis=basis,
                categories=["cybersecurity"],
                tags=[t.lower() for t in c.get("cveTags", []) if isinstance(t, str)][:10],
                verification=self.config.verification,
                canonical_key=f"cve:{cve}",
                raw={"vulnStatus": c.get("vulnStatus"), "sourceIdentifier": c.get("sourceIdentifier")},
                vulnerability=payload,
            )
        ]
