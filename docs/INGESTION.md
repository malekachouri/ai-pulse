# AI Pulse — Ingestion engine

Automated, idempotent collection from **official, machine-readable** sources only. AI Pulse never scrapes
HTML pages and never invents a missing value (date, severity, CVSS, status, remediation).

## Architecture

```
Celery Beat ──every 60 s──▶ dispatch_due_sources ──▶ ingest_source(source_id)  (Celery worker, queue "ingestion")
                                                         │
          pg_try_advisory_lock(source)  ── one run per source across all workers
                                                         │
   connector.fetch(checkpoint) → normalize() → validate() → deduplicate() → save() → reconcile()
                                                         │
     one DB transaction: articles + typed rows + checkpoint + job stats + source health
```

* **Schedule lives in Postgres.** A source is due when `last run + poll_interval × 2^failures` has passed
  (backoff capped at 24 h). Admin changes to `enabled` / `poll_interval_minutes` apply on the next tick.
* **Retries.** Each HTTP request retries 429/5xx/network errors up to 4× with exponential backoff + full
  jitter, honouring `Retry-After`. A failed *job* is retried by the worker after 1, 2, 4 … minutes
  (`INGESTION_MAX_ATTEMPTS`, default 3). Stuck `running` jobs older than 1 h are marked failed.
* **Rate limits** are per host and shared across workers through Redis (NVD 5 req/30 s without key,
  50 with key; arXiv 1 req/3 s; GitHub search 9/min; others 30/min). Overridable per source via
  `config.rate_limit = {"limit": n, "period": seconds}`.
* **Checkpointing.** ETag / Last-Modified (RSS, KEV), last-published (arXiv, HF models per org),
  last-modified window (NVD), last-updated per repo (GitHub issues/releases). Saved only with the data.
* **Idempotency.** Articles upsert on `(source_id, external_id)`; an unchanged content hash is a no-op.
  Typed rows upsert on natural keys with `INSERT … ON CONFLICT` + row lock. Re-running a job is safe.
* **Duplicates.** Each item has a `canonical_key` (`cve:…`, `arxiv:…`, `incident:…`, or the canonical URL).
  A new article with a key already present from another source is stored but linked via
  `duplicate_of_id`, so feeds show it once (e.g. a CVE from NVD and CISA KEV; a paper on arXiv and HF).
* **Merging facts.** Typed rows never overwrite a known value with an unknown one. Example: CISA KEV adds
  `known_exploited`, due date and required action to a CVE without touching NVD's CVSS.

## Shared normalized format (`app/ingestion/normalized.py`)

Every record carries: original URL, source (name/type via `Source`), publication date if provided,
collection timestamp, content hash, categories (≥ 1), verification status, plus optional typed payloads
(`vulnerability`, `incident`, `paper`, `release`, `repository`, `tool`, `issue`, `bug`). Original text is
stored in `articles.content`; AI output is stored separately in `ai_analyses` (Phase 5).

## Validation (records failing these are rejected and logged on the job as `stage: validate`)

* missing title · URL not absolute http(s) · no category · publication date > 1 day in the future ·
  severity without a documented basis · malformed CVE id.

## Sources (seeded by migration 0003; manage them on **Admin → Ingestion** or `/api/v1/admin/sources`)

Live-checked on 2026-11-09 against the real endpoints unless noted.

| Area | Source | Connector | Notes |
|---|---|---|---|
| AI | OpenAI News RSS | `rss` | official feed |
| AI | Google DeepMind blog RSS | `rss` | official feed |
| AI | Hugging Face blog RSS | `rss` | official feed |
| AI | Official model uploads on Hugging Face (Meta, Mistral AI, Google, Microsoft, Qwen, DeepSeek) | `hf_models` | Hub API, per-org checkpoint; a new repo is reported as "published", not as a "major release" |
| AI | AI lab GitHub releases (Meta Llama, Mistral, Anthropic SDK) | `github_releases` | *not live-checked here (sandbox blocks per-repo GitHub API)* |
| Research | arXiv cs.CL / cs.LG / cs.AI | `arxiv` | 1 req / 3 s per arXiv terms |
| Research | Hugging Face daily papers | `hf_daily_papers` | linked to the arXiv record as a duplicate |
| GitHub | Rising AI / DevOps repositories | `github_trending` | **GitHub has no trending API** — Search API ranked by stars, plus AI Pulse's daily star snapshots → `stars_delta_7d` (null until 7 days of history exist) |
| GitHub | AI framework & cloud-native releases | `github_releases` | Kubernetes, Moby, containerd, Helm, Prometheus, Argo CD, Istio, Cilium, vLLM, Transformers, LangChain, Ollama, LlamaIndex, pgvector; *not live-checked here* |
| GitHub | Bug & security issues | `github_issues` | open + closed; severity only from labels (basis recorded), else `unknown`; unverified until a maintainer label confirms; *not live-checked here* |
| Security | NVD CVE API 2.0 | `nvd` | 120-day windows, pagination, NVD "Primary" score preferred, Rejected CVEs skipped |
| Security | CISA KEV | `cisa_kev` | articles for entries added in the last 30 days; all entries flag their CVE |
| Security | Kubernetes official CVE feed | `kubernetes_cve_feed` | vendor advisories; CVSS only from the SRC's own rating line |
| Status | Google Cloud Service Health | `gcp_status` | `end` present → resolved, otherwise investigating |
| Status | AWS Health (public RSS) | `aws_status_rss` | feed keeps old events open-ended: only entries updated < 24 h ago can be open; older → `unknown` |
| Status | Azure status RSS | `azure_status_rss` | lists current issues only; vanished items → `unknown` (resolution not claimed) |
| Status | GitHub, OpenAI, Docker, Anthropic status | `statuspage` | Atlassian Statuspage API; provider's own status and impact. Anthropic moved to `status.claude.com` — *not live-checked here* |
| DevOps | Kubernetes, Docker, CNCF blogs; AWS What's New; Google Cloud release notes | `rss` | GCP notes moved to `docs.cloud.google.com` — *not live-checked here* |

### Deliberately not included

* **Anthropic, Mistral AI and Meta AI news pages** have no official RSS/API (`/news/rss.xml` returns 404).
  AI Pulse does not scrape them; their releases are covered via official Hugging Face orgs and GitHub repos.
* **AWS Health API** (account-specific, needs AWS credentials) — the public dashboard feed is used instead.

## Credentials (all optional)

| Variable | Effect |
|---|---|
| `GITHUB_TOKEN` | fine-grained token, public-repo read-only: 60 → 5,000 requests/hour |
| `NVD_API_KEY` | 5 → 50 requests per 30 s (free key from NVD) |

## Operations

```bash
python -m app.cli sources          # list sources, failures and last success
python -m app.cli ingest nvd-cve   # run one source now, in-process (no Celery)
python -m app.cli sync-sources     # add catalog sources missing from the DB (never overwrites edits)
celery -A app.workers.celery_app worker -Q ingestion -l info
celery -A app.workers.celery_app beat -l info
```

Admin API: `GET /admin/ingestion/status`, `GET /admin/connectors` (JSON Schema of each connector's
options), `POST /admin/sources/{id}/run`, `POST /admin/jobs/{id}/retry`, `PATCH /admin/sources/{id}`
(`enabled`, `poll_interval_minutes`, `config` — validated against the connector — and
`reset_checkpoint`). Metrics: `aipulse_ingestion_runs_total`, `aipulse_ingestion_items_total`,
`aipulse_ingestion_duration_seconds`.

## Adding a source

1. Prefer an existing connector (`rss`, `statuspage`, …): `POST /admin/sources` with its `config`.
2. For a new API, subclass `Connector`, implement `fetch()` and `normalize()`, register it in
   `app/ingestion/connectors/__init__.py`, and add a test using a recorded response in
   `tests/fixtures/ingestion/`.
