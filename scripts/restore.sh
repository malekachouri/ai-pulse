#!/usr/bin/env bash
# Restores a backup made by scripts/backup.sh (or the backup service) into the running stack.
#   scripts/restore.sh backups/aipulse-20260101T000000Z.dump [--yes]
# Stops the writers (api, worker, beat), recreates the database, restores, runs migrations, restarts.
set -euo pipefail
cd "$(dirname "$0")/.."
FILE="${1:?usage: scripts/restore.sh <file.dump> [--yes]}"
COMPOSE=(docker compose ${COMPOSE_FILES:-})
DB="${POSTGRES_DB:-aipulse}"
APP_USER="${APP_DB_USER:-aipulse}"
[[ -f "$FILE" ]] || { echo "No such file: $FILE" >&2; exit 1; }
if [[ -f "$FILE.sha256" ]]; then
  ( cd "$(dirname "$FILE")" && sha256sum -c "$(basename "$FILE").sha256" )
fi
if [[ "${2:-}" != "--yes" ]]; then
  read -r -p "This REPLACES database '$DB' with $FILE. Type the database name to continue: " answer
  [[ "$answer" == "$DB" ]] || { echo "Aborted."; exit 1; }
fi
"${COMPOSE[@]}" stop api worker beat
psql_admin() { "${COMPOSE[@]}" exec -T postgres sh -c 'PGPASSWORD="$(cat /run/secrets/postgres_password)" psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -U postgres "$@"' psql "$@"; }
psql_admin -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB' AND pid <> pg_backend_pid();" >/dev/null
psql_admin -d postgres -c "DROP DATABASE IF EXISTS \"$DB\";"
psql_admin -d postgres -c "CREATE DATABASE \"$DB\" OWNER \"$APP_USER\";"
psql_admin -d "$DB" -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS pg_stat_statements; ALTER SCHEMA public OWNER TO \"$APP_USER\"; REVOKE ALL ON SCHEMA public FROM PUBLIC;"
# Restore as the application role so every object keeps the right owner.
"${COMPOSE[@]}" exec -T postgres sh -c \
  'PGPASSWORD="$(cat /run/secrets/app_db_password)" pg_restore -h 127.0.0.1 -U "$1" -d "$0" --no-owner --exit-on-error' \
  "$DB" "$APP_USER" < "$FILE"
"${COMPOSE[@]}" run --rm migrate
"${COMPOSE[@]}" up -d api worker beat
echo "Restore of $FILE completed."
