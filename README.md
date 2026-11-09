# AI Pulse

**AI & Technology Intelligence Platform** — one place to track AI models and research, tools and
GitHub activity, software bugs and outages, CVEs, and cloud/DevOps changes, with original sources,
timestamps and verification status on every item.

> Status: **Phases 1–4 of 9 complete** — architecture, database, auth, the full REST API, the web
> interface and automated collection from 27 official sources. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and roadmap.
> Data starts flowing as soon as the worker and Beat containers run (see [docs/INGESTION.md](docs/INGESTION.md)).
> AI Pulse never presents demo content as real data — see *Demo mode* below.

## Stack

| Layer | Technology |
|---|---|
| Web | Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS 4 · shadcn/ui (Radix) · Lucide · Recharts · TanStack Query |
| API | FastAPI · Pydantic 2 · SQLAlchemy 2 (async) · Alembic |
| Data | PostgreSQL 16 + pgvector + full-text search · Redis · Celery workers + Beat |
| Ops | Docker · GitHub Actions · Prometheus metrics (Grafana in Phase 8) |

## Quick start (Docker)

```bash
cp .env.example .env
# set JWT_SECRET (python -c "import secrets; print(secrets.token_urlsafe(48))") and POSTGRES_PASSWORD
docker compose up --build -d
docker compose exec api python -m app.cli create-admin --email you@example.com
```

- Web app: <http://localhost:3000> · ingestion dashboard: **Admin → Ingestion** (admin/analyst)
- Collect immediately instead of waiting for the schedule: `docker compose exec api python -m app.cli ingest nvd-cve`
- API docs: <http://localhost:8000/docs> · readiness: <http://localhost:8000/health/ready>

The browser only talks to the Next.js origin; `/api/v1/*` is proxied to FastAPI server-side, so the
httpOnly refresh cookie stays first-party and no API address or key is exposed to clients.

## Local development

Requires Python 3.12+, Node 22+, and PostgreSQL 16 with the `vector` extension available.

```bash
# API
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aipulse
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))") COOKIE_SECURE=false
alembic upgrade head
uvicorn app.main:app --reload            # http://localhost:8000
# collection (needs Redis): in two more terminals
celery -A app.workers.celery_app worker -Q ingestion -l info
celery -A app.workers.celery_app beat -l info
# or run one source in-process without Celery:
python -m app.cli ingest openai-news
```

```bash
# Web (second terminal)
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

### Demo mode (UI preview without a backend)

```bash
cd frontend
NEXT_PUBLIC_DEMO_MODE=true npm run dev
```

Serves built-in **fictional** sample data so you can see populated screens. Every demo item is
titled `[DEMO] …`, comes from a "Demo source", links to `example.com`, and a permanent banner reads
*"DEMO MODE — all items below are fictional sample data"*. Never enable it in production.

## Tests & checks

```bash
# Backend — integration tests against real Postgres, built from the Alembic migrations
cd backend
createdb aipulse_test   # needs pgvector installed on the server
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aipulse_test pytest -q
ruff check app tests alembic && ruff format --check app tests alembic
```

```bash
# Frontend
cd frontend
npm run lint && npm run typecheck && npm test && npm run build
```

## What's implemented

**Phase 1 — foundation**
- Data model for all 20 domain entities (+ tokens, read state, audit log) with constraints, FTS and
  HNSW vector indexes; one reversible migration.
- Auth: Argon2id, JWT access tokens, rotating httpOnly refresh cookie with reuse detection, password
  change/reset, role-based access. Admin source management (audited). Health, metrics, structured logs.

**Phase 2 — web interface**
- App shell: collapsible sidebar (remembered per browser), mobile drawer, global search (`/` to focus),
  notification center with unread badge, profile menu, dark-navy / light / system themes.
- All 13 sidebar pages plus search, sign-in, registration, forgot/reset password.
- Overview dashboard: KPI cards, 14-day activity chart, distribution by type, trending technologies,
  activity timeline, AI announcements, security alerts, recent failures, daily briefing preview.
- Reusable article card: source + verification status, published vs collected time, categories,
  severity **with its documented basis**, AI Pulse importance score (explicitly *not* CVSS),
  AI summary labelled *AI-generated*, original-source link, bookmark and read/unread.
- Filters synced to the URL: full-text search, type, category, source, date range (presets/custom),
  severity, minimum importance, sort (latest/importance/relevance), pagination.
- Bookmarks, notifications, preferences (interests, followed tech/repos/providers, alert severity,
  briefing frequency/time/timezone) and briefing endpoints added to the API to back these pages.
- Loading skeletons, empty states, error states with retry, and sign-in prompts on every page;
  every chart has a data-table view.

**Phase 3 — complete REST API**
- Typed modules with module-specific filters, whitelisted `sort=-field` sorting and pagination:
  `/models` (+ releases), `/tools`, `/research`, `/github` (repositories, issues), `/bugs`,
  `/security` (vulnerabilities, stats), `/incidents`.
- Incidents are only `is_active` when the provider's status page says unresolved **and** AI Pulse
  re-verified it within 2 hours; older unresolved ones are flagged `status_is_stale`.
- `/search`: ranked keyword search with highlighted plain-text snippets (semantic/hybrid return 501
  until the AI engine generates embeddings).
- Admin: user list/filter, role and activation changes (audited, no self-lockout, last admin protected,
  deactivation revokes sessions), roles with counts, ingestion job history, audit log.
- Migration 0002 adds indexes for the new filters. Frontend: search page with highlights, active
  incidents (Bugs, DevOps), CVE stats strip (Security), rising repos (GitHub), tracked models (Models).

**Phase 4 — automated ingestion**
- 14 connectors, each implementing `fetch / normalize / validate / deduplicate / save / log_errors`,
  covering 27 official sources (seeded): OpenAI, Google DeepMind and Hugging Face blogs; official
  Hugging Face model uploads (Meta, Mistral AI, Google, Microsoft, Qwen, DeepSeek); arXiv; HF papers;
  GitHub releases, issues and a documented "rising repositories" alternative (no trending API exists);
  NVD; CISA KEV; Kubernetes CVE feed; Google Cloud, AWS and Azure status; GitHub/OpenAI/Docker/Anthropic
  status pages; Kubernetes, Docker, CNCF, AWS and Google Cloud announcement feeds.
- Celery workers + Beat, DB-driven schedule with failure backoff, HTTP retries with jitter and
  `Retry-After`, Redis-shared per-host rate limits, checkpoints, conditional GETs, per-source locks,
  atomic idempotent saves, cross-source duplicate linking, failed-job tracking with retries, source health.
- Admin → Ingestion dashboard: health, last runs, failures, enable/disable, interval, run now, retry.
- Verified against the live sources: 19 of them collected ~2,800 real items with zero invalid records;
  a second run created no duplicates. Tests use recorded real responses (46 new tests).
