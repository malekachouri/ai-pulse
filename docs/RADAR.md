# Bugs & Failures Radar

The radar (`/bugs` in the UI, `GET /api/v1/radar/summary` in the API) brings together three kinds of
operational intelligence. Every row links to its original source and shows when AI Pulse last verified it.

## Accuracy rules

| Rule | How it is enforced |
|---|---|
| No "critical" without a documented basis | Severity is only displayed when `severity_basis` is set (NVD CVSS, GHSA severity, vendor label, project label). Otherwise the UI shows **Not rated**. The "critical bugs" KPI and bug alerts require a basis. |
| Never mark an incident active from old data | `state=current` requires the provider to report it unresolved **and** `last_verified_at` within 2 h. Unresolved but not re-verified → `unverified`. AWS RSS entries older than 24 h and Azure entries that disappear from the feed get status *unknown*. |
| "Fixed" means fixed | A bug's `resolution=fixed` needs the issue to be closed as completed **and** a merged pull request or closing commit found in the GitHub timeline. Otherwise `completed`, `not_planned`, `duplicate` or `unknown`. |
| Mitigation only from official sources | Remediation comes from NVD / CISA KEV `requiredAction` / GitHub Security Advisory patched versions. It is never generated. |
| Show references | Vulnerability lists include the NVD/vendor references, remediation and verification time. |

## Data

**Bugs** (`software_bugs`): title, repository, issue number, URL, status, severity and basis, labels,
created and updated dates, affected versions (extracted from "Version:"-style lines in the issue body),
fix URL, `fix_merged_at`, `resolution`, `last_verified_at`. Collected by the GitHub issues connector.
For closed issues it looks up the timeline (`fix_lookups` per run, 15 by default).

**Failures** (`service_incidents`): provider, affected services, provider status, start and resolution,
impact, official URL, update log. Computed fields: `state` (current, historical or unverified),
`categories`, `duration_minutes`.

Categories use word-start term matching, so `rds` never matches "Mastercards". The terms are shared
between the Python labels and the PostgreSQL filter, so the two always agree. The categories are:

- ai_provider
- cloud
- api
- database
- kubernetes_docker
- infrastructure
- developer_platform

**Vulnerabilities** (`security_vulnerabilities`): CVE, CVSS and vector, severity and basis, affected
products, CISA KEV exploitation and date, published date, patch availability, remediation, references
and CWE. Sources:

- NVD
- CISA KEV
- Kubernetes CVE feed
- **GitHub Security Advisories** (new `github_advisories` connector, for the pip, npm, go and maven ecosystems). It skips withdrawn advisories. Advisories that have no CVE are kept as articles only.

## API

- `GET /radar/summary?days=30` (7–90). Returns:
  - critical bugs
  - new critical or high vulnerabilities (7 days)
  - vulnerabilities newly added to KEV
  - active, resolved (14 days) and unverified incidents
  - severity chart
  - most affected technologies
  - incident history per provider per day
  - 8 weeks of weekly stats
- `GET /bugs` adds two filters: `resolution` and `reported_within_days`.
- `GET /incidents` adds two filters: `state=current|historical|unverified` and `category`.
- `GET /security/vulnerabilities` items include `remediation`, `references` and `last_verified_at`.
- `POST /admin/alerts/run` (staff only, audited) evaluates the alert rules immediately.

## Alerts

`user_preferences.alert_settings` stores the alert settings. You edit them in **Settings → Alerts**.
Celery runs `aipulse.evaluate_alerts` every 5 minutes, and again after each successful ingestion run.

| Rule | Fires when |
|---|---|
| `critical_cves` | A new critical CVE has a documented basis and CVSS ≥ `min_cvss` (default **9.5**; `null` = any critical CVE). |
| `exploited` | A CVE was added to CISA KEV in the last 2 days. |
| `critical_bugs` | A critical bug has a basis, in `bug_projects` or in the user's followed repositories. |
| `outages` | An incident is **currently active**, its impact is ≥ `outage_min_impact`, and it is from one of `outage_providers` (all providers when that list is empty). Unknown impact passes only at the "minor" threshold. |
| `watched_tech` | An advisory matches the user's followed technologies or providers, at or above their notification severity. |

Each event is notified once per user. A unique key (`cve:<id>:new`, `cve:<id>:kev`, `bug:<id>`,
`incident:<id>`) prevents duplicates, so running the engine twice never notifies twice.

## Limitations

- The GitHub REST endpoints (issues timeline and advisories) are tested with recorded and mocked responses. The development sandbox could not reach them.
- Statuspage impact is used as provided. Google Cloud severities are mapped as follows: `SERVICE_OUTAGE` → critical, `SERVICE_DISRUPTION` → major, other values → minor.
- Alerts are in-app notifications. Email and web-push delivery is part of Phase 7.
