#!/usr/bin/env bash
# On-demand logical backup of the AI Pulse database from the running Compose stack.
#   scripts/backup.sh [output-dir]      (default ./backups)
# Produces <db>-<UTC timestamp>.dump (pg_dump custom format, compressed) + .sha256, and verifies it.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT_DIR="${1:-./backups}"
read -r -a COMPOSE_EXTRA <<< "${COMPOSE_FILES:-}"  # e.g. "-f docker-compose.yml -f docker-compose.prod.yml"
COMPOSE=(docker compose "${COMPOSE_EXTRA[@]}")
DB="${POSTGRES_DB:-aipulse}"
mkdir -p "$OUT_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
file="$OUT_DIR/${DB}-${ts}.dump"
# shellcheck disable=SC2016 # evaluated inside the container, on purpose
"${COMPOSE[@]}" exec -T postgres sh -c \
  'PGPASSWORD="$(cat /run/secrets/postgres_password)" pg_dump -h 127.0.0.1 -U postgres --format=custom --compress=6 --no-owner "$0"' \
  "$DB" > "$file.partial"
mv "$file.partial" "$file"
( cd "$OUT_DIR" && sha256sum "$(basename "$file")" > "$(basename "$file").sha256" )
# Verify the archive can be read by pg_restore before declaring success.
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "$file" > /dev/null
echo "Backup written: $file ($(du -h "$file" | cut -f1))"
