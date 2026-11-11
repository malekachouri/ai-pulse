#!/usr/bin/env bash
# Restores a backup made by scripts/backup.sh (or the backup service) into the running stack.
#   scripts/restore.sh backups/aipulse-20260101T000000Z.dump [--yes]
#   scripts/restore.sh --from-offsite [latest|aipulse-20260101T000000Z.dump] [--yes]
#       downloads and decrypts the offsite copy (infra/backup/offsite.sh, via the backup service's
#       image and secrets), verifies its checksum, then restores it the same way.
#
# Safe by construction: the dump is restored into a NEW database first. Only when that succeeds are the
# writers stopped and the databases swapped; the previous database is kept as <db>_pre_restore_<ts> for
# rollback (drop it once you are satisfied). A failed restore leaves the current database untouched.
set -euo pipefail
cd "$(dirname "$0")/.."
USAGE="usage: scripts/restore.sh <file.dump> [--yes] | --from-offsite [latest|<name>.dump] [--yes]"
read -r -a COMPOSE_EXTRA <<< "${COMPOSE_FILES:-}"  # e.g. "-f docker-compose.yml -f docker-compose.prod.yml"
COMPOSE=(docker compose "${COMPOSE_EXTRA[@]}")
if [[ "${1:-}" == "--from-offsite" ]]; then
  shift
  WANT="latest"
  if [[ -n "${1:-}" && "$1" != "--yes" ]]; then WANT="$1"; shift; fi
  offsite() {
    "${COMPOSE[@]}" run --rm -T --no-deps --entrypoint /bin/bash backup /backup/offsite.sh "$@"
  }
  NAME="$(offsite fetch-sum "$WANT" | awk '{print $2}' | xargs -r basename)"
  [[ "$NAME" =~ ^[A-Za-z0-9._-]+\.dump$ ]] || { echo "No usable offsite backup ($WANT)" >&2; exit 1; }
  mkdir -p backups/offsite
  echo "0/4 downloading and decrypting offsite copy $NAME"
  offsite fetch-sum "$NAME" | awk -v n="$NAME" '{print $1 "  " n}' > "backups/offsite/$NAME.sha256"
  offsite fetch "$NAME" > "backups/offsite/$NAME.partial"
  mv "backups/offsite/$NAME.partial" "backups/offsite/$NAME"
  set -- "backups/offsite/$NAME" "$@"
fi
FILE="${1:?$USAGE}"
DB="${POSTGRES_DB:-aipulse}"
APP_USER="${APP_DB_USER:-aipulse}"
TS="$(date -u +%Y%m%d%H%M%S)"
STAGING="${DB}_restore_${TS}"
PREVIOUS="${DB}_pre_restore_${TS}"

[[ -f "$FILE" ]] || { echo "No such file: $FILE" >&2; exit 1; }
if [[ -f "$FILE.sha256" ]]; then
  ( cd "$(dirname "$FILE")" && sha256sum -c "$(basename "$FILE").sha256" )
fi
if [[ "${2:-}" != "--yes" ]]; then
  read -r -p "Replace database '$DB' with $FILE? Type the database name to continue: " answer
  [[ "$answer" == "$DB" ]] || { echo "Aborted."; exit 1; }
fi

psql_admin() {
  # shellcheck disable=SC2016 # evaluated inside the container, on purpose
  "${COMPOSE[@]}" exec -T postgres sh -c \
    'PGPASSWORD="$(cat /run/secrets/postgres_password)" psql -v ON_ERROR_STOP=1 -q -h 127.0.0.1 -U postgres "$@"' psql "$@"
}

echo "1/4 restoring into staging database $STAGING"
psql_admin -d postgres -c "CREATE DATABASE \"$STAGING\" OWNER \"$APP_USER\";"
psql_admin -d "$STAGING" -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS pg_stat_statements; ALTER SCHEMA public OWNER TO \"$APP_USER\"; REVOKE ALL ON SCHEMA public FROM PUBLIC;"
# As the application role, so every object keeps the right owner. Extensions already exist (created by the
# superuser above); --no-comments skips COMMENT ON EXTENSION, which only an extension's owner may run.
# shellcheck disable=SC2016 # evaluated inside the container, on purpose
if ! "${COMPOSE[@]}" exec -T postgres sh -c \
  'PGPASSWORD="$(cat /run/secrets/app_db_password)" pg_restore -h 127.0.0.1 -U "$1" -d "$0" --no-owner --no-comments --exit-on-error' \
  "$STAGING" "$APP_USER" < "$FILE"; then
  psql_admin -d postgres -c "DROP DATABASE IF EXISTS \"$STAGING\";"
  echo "Restore failed; database '$DB' was not modified." >&2
  exit 1
fi
tables="$(psql_admin -d "$STAGING" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname='public'")"
[[ "$tables" -gt 0 ]] || { psql_admin -d postgres -c "DROP DATABASE \"$STAGING\";"; echo "Empty restore, aborted" >&2; exit 1; }

echo "2/4 stopping writers (api, worker, beat)"
"${COMPOSE[@]}" stop api worker beat

echo "3/4 swapping databases ($DB -> $PREVIOUS, $STAGING -> $DB)"
psql_admin -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$DB', '$STAGING') AND pid <> pg_backend_pid();" >/dev/null
psql_admin -d postgres -c "ALTER DATABASE \"$DB\" RENAME TO \"$PREVIOUS\";"
psql_admin -d postgres -c "ALTER DATABASE \"$STAGING\" RENAME TO \"$DB\";"

echo "4/4 migrating to the current schema and restarting"
"${COMPOSE[@]}" run --rm migrate
"${COMPOSE[@]}" up -d api worker beat
echo "Restore of $FILE completed ($tables tables). Previous database kept as '$PREVIOUS':"
echo "  rollback: stop api/worker/beat, rename databases back;  cleanup: DROP DATABASE \"$PREVIOUS\";"
