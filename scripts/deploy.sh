#!/usr/bin/env bash
# Rolls out IMAGE_TAG on this host (run from the deployment directory; used by .github/workflows/deploy.yml).
#   IMAGE_PREFIX=ghcr.io/<owner>/ai-pulse IMAGE_TAG=<sha> [PUBLIC_URL=https://pulse.example.com] scripts/deploy.sh
# Steps: pull images, pre-deployment backup, migrate, restart services, wait until healthy, smoke test.
# On any failure after the backup it rolls back to the previously deployed tag (recorded in .deployed_tag).
# Note: migrations are forward-only in production; a rollback keeps the new schema, so migrations must be
# backward compatible with the previous release (expand/contract). The pre-deployment dump is the last resort.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${IMAGE_PREFIX:?}" "${IMAGE_TAG:?}"
read -r -a EXTRA_PROFILES <<< "${DEPLOY_PROFILES:---profile edge}"
PROFILES=(--profile monitoring --profile backup "${EXTRA_PROFILES[@]}")
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml "${PROFILES[@]}")
export COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
PREVIOUS="$(cat .deployed_tag 2>/dev/null || true)"

[[ -f .env && -d secrets ]] || { echo "Missing .env or secrets/ on this host (see docs/DEPLOYMENT.md)" >&2; exit 1; }
if [[ " ${PROFILES[*]} " == *" edge "* ]] && ! grep -Eq '^DOMAIN=[^[:space:]#]+' .env; then
  echo "DOMAIN must be set in .env for the edge profile (public hostname for HTTPS)" >&2; exit 1
fi
export IMAGE_PREFIX IMAGE_TAG

echo "==> pulling $IMAGE_PREFIX/*:$IMAGE_TAG"
"${COMPOSE[@]}" pull --quiet

if "${COMPOSE[@]}" ps --status running -q postgres | grep -q .; then
  echo "==> pre-deployment backup"
  ./scripts/backup.sh backups/pre-deploy
fi

rollback() {
  echo "!!> deployment of $IMAGE_TAG failed" >&2
  "${COMPOSE[@]}" logs --no-color --tail 100 api worker beat web >&2 || true
  if [[ -n "$PREVIOUS" && "$PREVIOUS" != "$IMAGE_TAG" ]]; then
    echo "!!> rolling back to $PREVIOUS" >&2
    IMAGE_TAG="$PREVIOUS" "${COMPOSE[@]}" up -d --wait --wait-timeout 300 api worker beat web || true
  fi
  exit 1
}
trap rollback ERR

echo "==> migrating"
"${COMPOSE[@]}" run --rm migrate
echo "==> rolling out"
"${COMPOSE[@]}" up -d --remove-orphans --wait --wait-timeout 300
echo "==> smoke test"
./scripts/smoke-test.sh "${PUBLIC_URL:-http://localhost:${WEB_PORT:-3000}}"
trap - ERR
echo "$IMAGE_TAG" > .deployed_tag
docker image prune -f --filter "until=168h" >/dev/null
echo "==> $IMAGE_TAG deployed (previous: ${PREVIOUS:-none})"
