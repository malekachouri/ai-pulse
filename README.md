# AI Pulse

**AI & Technology Intelligence Platform** — one place to track AI models and research, tools and
GitHub activity, software bugs and outages, CVEs, and cloud/DevOps changes, with original sources,
timestamps and verification status on every item.

> Status: **Phase 1 of 9 complete** (architecture, database, auth, core API). See
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and roadmap. No data sources are
> connected yet, so lists are empty until Phase 4. AI Pulse never ships demo content as real data.

## Stack

FastAPI · SQLAlchemy 2 (async) · Alembic · PostgreSQL 16 + pgvector · Redis/Celery (Phase 4) ·
Next.js + Tailwind + shadcn/ui (Phase 2) · Prometheus/Grafana (Phase 8) · GitHub Actions

## Quick start (Docker)

```bash

cp .env.example .env
# set JWT_SECRET (python -c "import secrets; print(secrets.token_urlsafe(48))") and POSTGRES_PASSWORD
docker compose up --build -d
docker compose exec api python -m app.cli create-admin --email you@example.com
```

API: <http://localhost:8000/docs> · readiness: <http://localhost:8000/health/ready>

## Local development (without Docker)

Requires Python 3.12+ and PostgreSQL 16 with the `vector` extension available.

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aipulse
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))") COOKIE_SECURE=false
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

Tests run against a real PostgreSQL database built from the Alembic migrations (including a
downgrade/upgrade round-trip):

```bash
cd backend
createdb aipulse_test   # needs pgvector installed on the server
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aipulse_test pytest -q
ruff check app tests alembic && ruff format --check app tests alembic
```

## Implemented in Phase 1

- Full data model for all 20 domain entities (+ tokens, read state, audit log), with constraints,
  indexes, full-text search column and HNSW vector index; one reversible migration.
- Auth: registration, login, Argon2id, JWT access tokens, rotating refresh cookie with reuse
  detection, logout, profile, password change, password reset, role-based access.
- `GET /api/v1/news` with full-text search, filters, sorting and pagination; per-user read state.
- `GET /api/v1/dashboard/summary` computed only from stored data.
- Admin source management (create/update/disable/delete, audited).
- Health/readiness probes, Prometheus metrics, structured logs, consistent error envelope.
- Dockerfile (non-root, healthcheck), docker-compose, GitHub Actions CI.
