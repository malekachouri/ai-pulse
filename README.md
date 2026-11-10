# AI Pulse

**AI & Technology Intelligence Platform**: one place to follow AI models and research, tools and
GitHub activity, software bugs and outages, vulnerabilities, and cloud/DevOps changes. Every item
keeps its original source, its publication and collection dates, and its verification status. What
an AI wrote is always labelled and kept apart from the facts.

> **Status: complete (phases 1–9).** Platform, ingestion from 28 official sources, AI engine,
> Bugs & Failures radar, personalised briefings and notifications, production tooling, and a full
> audit with every reproducible bug fixed: see [docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md) for
> what was verified, test results, security findings and remaining limitations. AI Pulse never shows
> demo content as real data.

## Features

- **Intelligence feeds:**
  - AI news, model releases, tools, research papers, GitHub repositories and issues;
  - bugs, CVEs (NVD, CISA KEV, GitHub Security Advisories), cloud and SaaS incidents, DevOps updates;
  - URL-synced filters, keyword / semantic / hybrid search.
- **AI engine** (optional, OpenAI, Anthropic or Ollama):
  - summaries, impact, recommended actions and learning topics;
  - grounding checks against the sources;
  - an explainable importance score (not CVSS);
  - "Ask AI Pulse": answers only from collected items, with citations.
- **Bugs & Failures radar.** Severity only with a documented basis, and incidents shown as active only
  when re-verified on the provider's status page.
- **Personalised briefings:**
  - daily, weekdays or weekly, in the user's timezone;
  - a computed "what changed since last time";
  - in-app notifications (critical alerts, releases, bugs, vulnerabilities, incidents, briefings) with per-kind preferences.
- **Administration:**
  - system health and usage statistics;
  - users and roles, sources, connector health;
  - job history and failed-task retries;
  - AI provider configuration and usage, audit log.
- **Production-ready operations:**
  - hardened containers, Docker Compose for development and production;
  - CI/CD with security gates;
  - Prometheus, Grafana and 17 alert rules;
  - rate limiting, secrets management, verified backups and restores.

## Stack

| Layer | Technology |
|---|---|
| Web | Node 26 · Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS 4 · shadcn/ui · TanStack Query · Recharts |
| API | Python 3.15 · FastAPI · Pydantic 2 · SQLAlchemy 2 (async) · Alembic |
| Data | PostgreSQL 16 + pgvector + full-text search + pg_trgm · Redis 8 |
| Background | Celery workers + Beat (DB-driven schedules) |
| Operations | Docker / Compose · Caddy (automatic HTTPS) · Prometheus · Alertmanager · Grafana · GitHub Actions (Trivy, CodeQL, pip-audit, npm audit, Dependabot) |

## Quick start (Docker)

The first two commands generate random secrets in `./secrets` (never committed) and copy the
non-secret settings from `.env.example`:

```bash
./scripts/generate-secrets.sh
```

```bash
cp .env.example .env
```

Build and start the stack, waiting until every service is healthy:

```bash
docker compose up -d --build --wait
```

Create your administrator account:

```bash
docker compose exec api python -m app.cli create-admin --email you@example.com
```

Check that everything works:

```bash
./scripts/smoke-test.sh http://localhost:3000
```

- Web app: <http://localhost:3000>. Administration: **Admin → Administration** (admin and analyst roles).
- Collect from a source right away instead of waiting for the schedule:

  ```bash
  docker compose exec api python -m app.cli ingest nvd-cve
  ```

- Add the monitoring stack (Grafana on <http://localhost:3001>, user `admin`, password in
  `secrets/grafana_admin_password`):

  ```bash
  docker compose --profile monitoring up -d
  ```

- Development with hot reload:

  ```bash
  docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
  ```

  See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

- Production on a server (registry images, HTTPS, monitoring, backups):

  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile edge --profile monitoring --profile backup up -d --wait
  ```

  See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

AI features are optional. Set `LLM_PROVIDER` / `LLM_MODEL` in `.env` and put the key in
`secrets/openai_api_key` or `secrets/anthropic_api_key` (see [docs/AI.md](docs/AI.md)). Without them,
deterministic analysis, ranking and keyword search still work.

## Documentation

| Document | Content |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | principles, system overview, layers, schema, API overview, security architecture, roadmap |
| [docs/API.md](docs/API.md) | conventions (auth, errors, pagination, rate limits) and the full endpoint reference |
| [docs/DATABASE.md](docs/DATABASE.md) | schema by domain, indexes, migrations workflow, roles, backups, configuration |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | dev stack, native setup, demo mode, tests and checks, generated files |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | server setup, secrets, CI/CD, monitoring and alerts, backups and restore, upgrades, scaling |
| [SECURITY.md](SECURITY.md) | reporting, threat model, controls, secret rotation, scanning |
| [CONTRIBUTING.md](CONTRIBUTING.md) | workflow, rules, checks, what a good pull request contains |
| [docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md) | final audit: verified features, fixed bugs, test results, security findings, limitations, credentials |
| [docs/INGESTION.md](docs/INGESTION.md) · [docs/AI.md](docs/AI.md) · [docs/RADAR.md](docs/RADAR.md) · [docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md) | module guides |

## Tests and checks

Backend tests run against a real PostgreSQL + pgvector database, built from the migrations.

```bash
cd backend && pytest -q
```

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

CI runs these on every pull request, together with:
- migrations round trip, dependency audits, Compose and Prometheus validation;
- image builds with a Trivy gate;
- an end-to-end smoke test of the full stack and a backup/restore drill.

See [docs/DEPLOYMENT.md §3](docs/DEPLOYMENT.md#3-cicd).

## Project history

| Phase | Delivered |
|---|---|
| 1 Foundation | architecture, full schema and migration, auth (Argon2id, JWT + rotating refresh cookie, RBAC), core API, Docker |
| 2 Web interface | app shell, 13 pages, dashboard, article cards, URL-synced filters, bookmarks, notifications, preferences, demo mode |
| 3 REST API | typed modules (models, tools, research, GitHub, bugs, security, incidents), keyword search, admin users/roles/jobs/audit |
| 4 Ingestion | 14 connectors / 27 official sources, Celery + Beat, retries, rate limits, checkpoints, dedup, source health ([INGESTION.md](docs/INGESTION.md)) |
| 5 AI engine | providers, 10-step pipeline with grounding checks, explainable scoring, hybrid search, RAG with citations ([AI.md](docs/AI.md)) |
| 6 Radar | bugs with fix tracking, incident states, GitHub advisories connector, configurable alerts ([RADAR.md](docs/RADAR.md)) |
| 7 Briefings & notifications | 10-section personalised briefings, per-user scheduling, notification center and preferences ([NOTIFICATIONS.md](docs/NOTIFICATIONS.md)) |
| 8 Production readiness | 7 hardened images, Compose dev/prod, CI/CD with Trivy/CodeQL/audits and signed provenance, Prometheus/Grafana/alerts, rate limiting, secrets, admin console, backups ([DEPLOYMENT.md](docs/DEPLOYMENT.md)) |
| 9 Audit | live runs of every source, API, browser (axe-core, both themes, all roles) and full-stack checks; 22 bugs fixed incl. SSRF via source URLs, undelivered password-reset emails, ingestion failure accounting, RAG retrieval and WCAG 2.1 AA contrast/structure ([AUDIT_REPORT.md](docs/AUDIT_REPORT.md)) |
