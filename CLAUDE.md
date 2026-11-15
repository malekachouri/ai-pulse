# AI Pulse: notes for Claude Code

AI Pulse collects AI, security and DevOps news from official sources, analyses it with an AI model and shows
it in a web app. Read [README.md](README.md) for the overview and [CONTRIBUTING.md](CONTRIBUTING.md) for the
rules; the module guides are in `docs/`.

## Layout

- `backend/`: FastAPI on Python 3.15, SQLAlchemy async, Alembic migrations, Celery worker and Beat
  (`app/ingestion` collects, `app/ai` analyses, `app/api/v1` serves, `app/cli.py` operational commands).
- `frontend/`: Next.js on Node 26 (App Router, TanStack Query, Vitest).
- `e2e/`: Playwright + axe-core browser tests. `infra/`: PostgreSQL + pgvector, Redis, Caddy, Prometheus,
  Grafana, backups. `scripts/`: checks, update, deploy, backup, restore.

## Commands

| Task | Command |
|---|---|
| All checks, Docker only | `./scripts/check.sh` (or `backend`, `frontend`, `smoke`; see `/check`) |
| Part of the backend tests | `./scripts/check.sh backend -k <name>` |
| Update the local stack | `./scripts/update.sh` (see `/update`) |
| Analyse one item again | `docker compose exec -T api python -m app.cli reanalyse <CVE-id>` (see `/reanalyse`) |
| Browser tests | `./scripts/e2e.sh --build` (needs Node 26 and Chromium; ~6 min) |
| Logs | `docker compose logs --tail 80 <api\|worker\|beat\|web>` |

The user runs AI Pulse on Windows 11 in WSL2 with Docker Engine (no Docker Desktop, no Python or Node on the
host) and Ollama on the host with a small model (`qwen2.5:3b`). Prefer commands that need only Docker, and
remember that local AI calls can take minutes.

## Rules that matter most

- Never invent data: every fact keeps its source URL and dates; AI text is stored and shown separately and
  labelled. AI output is grounded (`app/ai/claims.py`): claims not supported by a cited source are removed.
- Tests for every change. Backend tests use a real PostgreSQL; mock only external HTTP. Never skip or weaken
  a test to get green.
- A migration (with a working `downgrade()`) for every model change.
- Docs in the same change: the module guide in `docs/`, `.env.example` for new settings, `SECURITY.md` for
  security changes. Ideas not built yet go to `docs/ROADMAP.md`.
- No secrets in code, tests or logs. Conventional Commit titles (`feat(ai): …`, `fix(auth): …`).
