#!/usr/bin/env bash
# Rotates a PostgreSQL password without downtime beyond a rolling restart of its clients.
#   scripts/rotate-db-password.sh app       # application role (api, worker, beat, migrate, backups/restores)
#   scripts/rotate-db-password.sh metrics   # postgres-exporter role
#   scripts/rotate-db-password.sh postgres  # superuser (backup service, restore script)
# Order: ALTER ROLE with the new password, then write the secret file (and derived database_url), then
# recreate the services that read it. The new password is passed to psql as a variable, never on a
# command line visible in `ps` or in shell history.
set -euo pipefail
cd "$(dirname "$0")/.."
read -r -a COMPOSE_EXTRA <<< "${COMPOSE_FILES:-}"
COMPOSE=(docker compose "${COMPOSE_EXTRA[@]}")
DB="${POSTGRES_DB:-aipulse}"
APP_USER="${APP_DB_USER:-aipulse}"
case "${1:-}" in
  app) role="$APP_USER"; file=secrets/app_db_password; services=(api worker beat) ;;
  metrics) role=metrics; file=secrets/metrics_db_password; services=(postgres-exporter) ;;
  postgres) role=postgres; file=secrets/postgres_password; services=(backup) ;;
  *) echo "usage: $0 app|metrics|postgres" >&2; exit 2 ;;
esac
new="$(openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-40)"
# NEWPW is passed by name (-e NEWPW), so its value never appears on a command line; psql reads it with
# \getenv and builds the statement with format(%I, %L) quoting.
# shellcheck disable=SC2016 # evaluated inside the container, on purpose
NEWPW="$new" "${COMPOSE[@]}" exec -T -e NEWPW postgres sh -c \
  'PGPASSWORD="$(cat /run/secrets/postgres_password)" psql -v ON_ERROR_STOP=1 -q -h 127.0.0.1 -U postgres -d "$0" -v role="$1"' \
  "$DB" "$role" <<'SQL'
\getenv pw NEWPW
SELECT format('ALTER ROLE %I PASSWORD %L', :'role', :'pw') \gexec
SQL
umask 077
printf '%s' "$new" > "$file"
chmod 644 "$file"
./scripts/generate-secrets.sh > /dev/null  # refreshes the derived database_url
# Services whose secret files changed must be recreated (Compose does not watch secret contents).
running=()
for s in "${services[@]}"; do
  "${COMPOSE[@]}" ps --status running -q "$s" 2>/dev/null | grep -q . && running+=("$s")
done
if ((${#running[@]})); then
  "${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 180 "${running[@]}"
fi
echo "Password of role '$role' rotated; recreated: ${running[*]:-none}"
