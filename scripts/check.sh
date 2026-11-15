#!/usr/bin/env bash
# Every check of the project, with Docker only (no Python or Node needed on this computer).
#   ./scripts/check.sh                   backend + frontend + smoke
#   ./scripts/check.sh backend           ruff, migrations round trip, pytest (throwaway PostgreSQL + Redis)
#   ./scripts/check.sh frontend          ESLint, TypeScript, Vitest, production build
#   ./scripts/check.sh smoke             the running stack, in its normal configuration
#   ./scripts/check.sh backend -k cli    extra arguments go to pytest (backend only)
# The backend and frontend checks run on a copy of the code inside a container: nothing is written to this
# folder and the running AI Pulse stack and its data are not touched. Exit code 1 when a check fails.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_IMAGE="python:3.15-slim-bookworm"
NODE_IMAGE="node:26-alpine"
PG_IMAGE="pgvector/pgvector:0.8.7-pg16"
REDIS_IMAGE="redis:7.4-alpine"
RUN_ID="aipulse-check-$$"

step() { printf '\n==> %s\n' "$*"; }

backend() {
  step "backend: starting a throwaway PostgreSQL + Redis"
  # shellcheck disable=SC2064 # expand now
  trap "docker rm -f $RUN_ID-db $RUN_ID-redis >/dev/null 2>&1; docker network rm $RUN_ID >/dev/null 2>&1; trap - RETURN" RETURN
  docker network create "$RUN_ID" > /dev/null
  docker run -d --rm --name "$RUN_ID-db" --network "$RUN_ID" -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=aipulse_test "$PG_IMAGE" > /dev/null
  docker run -d --rm --name "$RUN_ID-redis" --network "$RUN_ID" "$REDIS_IMAGE" > /dev/null
  local db="postgresql+asyncpg://postgres:postgres@$RUN_ID-db:5432/aipulse_test"
  step "backend: lint, migrations, tests (the first run downloads the packages: a few minutes)"
  # The pip cache volume makes later runs faster; it holds downloaded packages only.
  docker run --rm --network "$RUN_ID" -v "$PWD:/src:ro" -v aipulse-check-pip-cache:/root/.cache/pip \
    -e TEST_DATABASE_URL="$db" -e DATABASE_URL="$db" -e REDIS_URL="redis://$RUN_ID-redis:6379/0" \
    -e DB_HOST="$RUN_ID-db" -e PYTHONDONTWRITEBYTECODE=1 -e PIP_ROOT_USER_ACTION=ignore -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
    "$PYTHON_IMAGE" sh -euc '
      mkdir -p /work && cp -r /src/backend /src/scripts /work/ && cd /work/backend
      pip install -q -r requirements-dev.txt
      # PostgreSQL only listens on TCP once its first-start initialisation is over.
      for i in $(seq 60); do python -c "import os, socket; socket.create_connection((os.environ[\"DB_HOST\"], 5432), 1)" 2>/dev/null && break; sleep 1; done
      echo "-- ruff"
      ruff check --config pyproject.toml app tests alembic docker ../scripts
      ruff format --check --config pyproject.toml app tests alembic docker ../scripts
      echo "-- migrations: upgrade, models in sync, downgrade, upgrade"
      alembic upgrade head && alembic check && alembic downgrade base && alembic upgrade head
      echo "-- pytest"
      pytest -q -p no:cacheprovider "$@"
    ' check "$@"
}

frontend() {
  step "frontend: lint, types, tests, build (the first run downloads the packages: a few minutes)"
  docker run --rm -v "$PWD/frontend:/src:ro" -v aipulse-check-npm-cache:/root/.npm \
    -e NEXT_TELEMETRY_DISABLED=1 -e npm_config_update_notifier=false "$NODE_IMAGE" sh -euc '
      mkdir -p /work && cd /src && tar --exclude=./node_modules --exclude=./.next -cf - . | tar -C /work -xf -
      cd /work && npm ci --no-audit --no-fund --loglevel=error
      npm run lint && npm run typecheck && npm test && npm run build
    '
}

smoke() {
  local files
  files="$(docker inspect ai-pulse-api-1 --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' 2>/dev/null || true)"
  if [[ "$files" == *docker-compose.e2e.yml* ]]; then
    step "smoke: the stack still runs with the e2e test settings (relaxed rate limits): restarting it normally"
    docker compose -f docker-compose.yml -f e2e/docker-compose.e2e.yml rm -sf mailpit > /dev/null 2>&1 || true
    docker compose up -d --no-build --wait --wait-timeout 300
  elif [[ -z "$files" ]]; then
    echo "smoke: the stack is not running. Start it first: docker compose up -d --wait" >&2
    return 1
  fi
  step "smoke: the running stack"
  ./scripts/smoke-test.sh "${SMOKE_URL:-http://localhost:3000}"
}

parts=()
while [[ $# -gt 0 && "$1" =~ ^(backend|frontend|smoke)$ ]]; do parts+=("$1"); shift; done
[[ ${#parts[@]} -gt 0 ]] || parts=(backend frontend smoke)
[[ $# -eq 0 || " ${parts[*]} " == " backend " ]] || { echo "pytest arguments need: check.sh backend <args>" >&2; exit 2; }

failed=()
for part in "${parts[@]}"; do
  if [[ "$part" == backend ]]; then backend "$@" || failed+=("$part"); else "$part" || failed+=("$part"); fi
done

echo
for part in "${parts[@]}"; do
  if [[ " ${failed[*]} " == *" $part "* ]]; then echo "FAIL $part"; else echo "ok   $part"; fi
done
[[ ${#failed[@]} -eq 0 ]]
