#!/usr/bin/env bash
# Browser end-to-end tests (Playwright + axe-core) against the production build of the full stack.
#   ./scripts/e2e.sh [--build] [playwright arguments...]
# Needs ./secrets and .env (scripts/generate-secrets.sh, cp .env.example .env), Node 26 and the Playwright
# browser (cd e2e && npm ci && npx playwright install chromium). Starts the stack with the test-only
# additions in e2e/docker-compose.e2e.yml, seeds labelled [E2E] items, creates a one-off admin, runs the
# tests and leaves the stack running for inspection (HTML report: cd e2e && npx playwright show-report).
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.yml -f e2e/docker-compose.e2e.yml)
BUILD=(--no-build)
if [[ "${1:-}" == "--build" ]]; then BUILD=(--build); shift; fi

echo "==> starting the stack (with mailpit and test rate limits)"
"${COMPOSE[@]}" up -d "${BUILD[@]}" --wait --wait-timeout 300 mailpit api worker beat web

echo "==> seeding labelled test data"
"${COMPOSE[@]}" exec -T api python - < e2e/seed.py
"${COMPOSE[@]}" exec -T api python -m app.cli ai-analyze --limit 100 > /dev/null

# A new admin per run: its password only exists in this process.
E2E_ADMIN_EMAIL="e2e-admin-$(date +%s)@example.com"
E2E_ADMIN_PASSWORD="$(openssl rand -hex 16)-Aa1"
export E2E_ADMIN_EMAIL E2E_ADMIN_PASSWORD
"${COMPOSE[@]}" exec -T -e ADMIN_PASSWORD="$E2E_ADMIN_PASSWORD" api \
  python -m app.cli create-admin --email "$E2E_ADMIN_EMAIL" --full-name "E2E Admin" > /dev/null

echo "==> running the browser tests"
cd e2e
[[ -d node_modules ]] || npm ci --no-audit --no-fund
export E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:${WEB_PORT:-3000}}"
export MAILPIT_URL="${MAILPIT_URL:-http://127.0.0.1:${MAILPIT_PORT:-8025}}"
npx playwright test "$@"
