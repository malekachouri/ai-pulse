#!/usr/bin/env bash
# Runs once, on an empty data directory, as the PostgreSQL superuser.
# - creates the extensions the schema needs (they require superuser),
# - creates the application role (login, NOT superuser) that owns the application database,
#   so the API, workers and migrations never run as superuser.
set -euo pipefail

read_secret() {  # VAR or VAR_FILE (Docker secrets)
  local var="$1" file_var="${1}_FILE"
  if [[ -n "${!file_var:-}" ]]; then tr -d '\r\n' < "${!file_var}"; else printf '%s' "${!var:-}"; fi
}

APP_DB_USER="${APP_DB_USER:-aipulse}"
APP_DB_PASSWORD="$(read_secret APP_DB_PASSWORD)"
if [[ -z "$APP_DB_PASSWORD" ]]; then
  echo "APP_DB_PASSWORD(_FILE) is required" >&2
  exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" -v db="$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
              :'app_user', :'app_password') \gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'db', :'app_user') \gexec
SELECT format('ALTER SCHEMA public OWNER TO %I', :'app_user') \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON DATABASE postgres FROM PUBLIC;
-- Read-only monitoring role for postgres-exporter (pg_monitor grants the statistics views).
SELECT 'CREATE ROLE metrics LOGIN PASSWORD NULL' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metrics') \gexec
GRANT pg_monitor TO metrics;
SQL

METRICS_PASSWORD="$(read_secret METRICS_DB_PASSWORD)"
if [[ -n "$METRICS_PASSWORD" ]]; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v pw="$METRICS_PASSWORD" <<'SQL'
SELECT format('ALTER ROLE metrics PASSWORD %L', :'pw') \gexec
SQL
fi
echo "AI Pulse: extensions and roles initialised"
