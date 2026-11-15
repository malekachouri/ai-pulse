#!/usr/bin/env bash
# Update a local AI Pulse to the latest code and check it.
#   ./scripts/update.sh            pull main, rebuild what changed, restart, run the smoke test
#   ./scripts/update.sh --no-pull  rebuild and restart the code as it is in this folder
# Database migrations run on their own when the stack starts (the `migrate` service). Your data, .env and
# ./secrets are kept. For a server, use scripts/deploy.sh instead (docs/DEPLOYMENT.md).
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n==> %s\n' "$*"; }

if [[ "${1:-}" != "--no-pull" ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "You have local changes to tracked files (git status). Commit or stash them first: git stash" >&2
    exit 1
  fi
  before="$(git rev-parse HEAD)"
  step "pulling the latest code"
  git pull --ff-only
  if [[ "$(git rev-parse HEAD)" == "$before" ]]; then
    echo "Already up to date."
  else
    echo "New changes:"
    git log --oneline --no-merges "$before..HEAD" | sed 's/^/  /'
    if ! git diff --quiet "$before" HEAD -- .env.example; then
      echo "Note: .env.example changed. New or changed settings (copy what you need into your .env):"
      git diff "$before" HEAD -- .env.example | grep '^+[A-Z_]*=' | sed 's/^+/  /' || true
    fi
  fi
fi

step "rebuilding and restarting (only what changed is rebuilt; the first build takes several minutes)"
docker compose up -d --build --wait --wait-timeout 600

step "checking the running app"
./scripts/smoke-test.sh ${SMOKE_URL:+"$SMOKE_URL"}

step "services"
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
