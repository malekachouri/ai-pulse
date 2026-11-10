# Development

There are two ways to work on AI Pulse:
- **Docker development stack**: everything runs in containers, with hot reload.
- **Native**: the API and web run on your machine; PostgreSQL and Redis run in Docker or locally.

Requirements: Docker with Compose v2.24+, and for native work Python 3.15+, Node 26 (LTS) and PostgreSQL 16
with the `vector` extension.

## Option A: Docker development stack

```bash
./scripts/generate-secrets.sh
```

```bash
cp .env.example .env
```

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Then:
- web on <http://localhost:3000> (Next.js dev server, hot reload);
- API on <http://localhost:8000/docs> (uvicorn `--reload` on `backend/app`);
- PostgreSQL on `localhost:5432` and Redis on `localhost:6379` (dev only; the data network itself stays internal).

The override sets `ENVIRONMENT=development`, `COOKIE_SECURE=false` and readable (non-JSON) logs.
Backend code is mounted read-only into the API, worker and Beat containers. Restart the workers after
changing task code:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart worker beat
```

Useful commands:

```bash
docker compose exec api python -m app.cli create-admin --email you@example.com
```

```bash
docker compose exec api python -m app.cli ingest nvd-cve
```

The second one runs one source now, in-process.

```bash
docker compose exec api python -m app.cli ai-analyze --limit 200
```

```bash
docker compose --profile monitoring up -d
```

The monitoring profile serves Grafana on <http://localhost:3001> (user `admin`, password in
`secrets/grafana_admin_password`) and Prometheus on <http://localhost:9090>.

## Option B: native

```bash
cd backend
```

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
```

```bash
cp .env.example .env
```

Set `DATABASE_URL` and `JWT_SECRET` in `.env`, then:

```bash
alembic upgrade head
```

```bash
uvicorn app.main:app --reload
```

For collection, which needs Redis, run the worker and Beat in two more terminals:

```bash
celery -A app.workers.celery_app worker -Q ingestion -l info
```

```bash
celery -A app.workers.celery_app beat -l info
```

Then the web app:

```bash
cd frontend && npm install
```

```bash
BACKEND_URL=http://localhost:8000 npm run dev
```

The browser only talks to the Next.js origin: `/api/v1/*` is rewritten to FastAPI, so the
`HttpOnly` refresh cookie stays first-party and no API address or key reaches the client.

### Demo mode (UI without a backend)

```bash
cd frontend && NEXT_PUBLIC_DEMO_MODE=true npm run dev
```

It serves built-in **fictional** data. Every item is titled `[DEMO] …`, links to `example.com`, and a
permanent banner says so. Never enable it in production; production images are built without it.

## Tests and checks

The CI pipeline runs all of these (see [DEPLOYMENT.md §3](DEPLOYMENT.md#3-cicd)).

Backend: the tests run against a real PostgreSQL + pgvector database, built from the Alembic
migrations, with a downgrade/upgrade round trip.

```bash
cd backend && createdb aipulse_test
```

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aipulse_test pytest -q
```

```bash
ruff check --config pyproject.toml app tests alembic docker ../scripts && ruff format --check --config pyproject.toml app tests alembic docker ../scripts
```

```bash
alembic upgrade head && alembic check && alembic downgrade base && alembic upgrade head
```

Frontend:

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

Whole stack, end to end, in the production configuration:

```bash
docker compose --profile monitoring --profile backup up -d --build --wait
```

```bash
./scripts/smoke-test.sh http://localhost:3000
```

Security:

```bash
pip install pip-audit && pip-audit -r backend/requirements.txt
```

```bash
(cd frontend && npm audit)
```

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.67.2 image --severity HIGH,CRITICAL --ignore-unfixed ai-pulse/api:local
```

## Generated files

| File | Source | Regenerate |
|---|---|---|
| `infra/grafana/dashboards/*.json` | `scripts/build-dashboards.py` | `python3 scripts/build-dashboards.py` |
| endpoint reference in `docs/API.md` | the FastAPI app | `cd backend && python ../scripts/build-api-docs.py` |
| `secrets/*` (never committed) | `scripts/generate-secrets.sh` | run it; `--force` rotates the rotatable ones |

CI fails when a generated file is out of date.

## Project layout and conventions

- Backend layers: `api` (routing, no SQL) → `services` (rules) → `repositories` (queries) → `models`.
  Pydantic schemas define every contract, and query parameters are strict models (unknown parameters → 422).
- Never present generated text as fact: AI output goes to `ai_analyses` and is labelled in the UI.
  Severity always needs a `severity_basis`.
- Configuration comes from environment variables and secret files only (`app/core/config.py`).
  Add new settings to `.env.example` (non-secret) or as a secret file in `scripts/generate-secrets.sh`
  and `docker-compose.yml`.
- New metrics: add them to `app/core/metrics.py` (derived state is collected at scrape time), a panel
  in `scripts/build-dashboards.py`, and an alert with a unit test in `infra/prometheus/` if it
  deserves one.
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for branches, commits and reviews.
