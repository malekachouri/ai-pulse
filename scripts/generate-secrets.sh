#!/usr/bin/env bash
# Creates ./secrets/* for docker compose (never committed: secrets/ is in .gitignore).
# Existing files are always kept, so running it again never changes a secret by accident.
#   --force  rotates the secrets that are safe to rotate by replacing the file: jwt_secret (signs every
#            user out), metrics_token and redis_password (+ derived redis_url / exporter file).
# Database and Grafana passwords are stored inside PostgreSQL / Grafana too, so replacing the file alone
# would lock the services out: rotate them with the procedure in SECURITY.md ("Rotating secrets").
# Optional third-party keys are created empty: put your keys in those files.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=secrets
FORCE=false
[[ "${1:-}" == "--force" ]] && FORCE=true
umask 077
mkdir -p "$DIR"

rand() { openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-"${1:-40}"; }
put() {  # put NAME VALUE [rotatable]: create if missing; with --force also replace rotatable secrets
  local f="$DIR/$1"
  if [[ -s "$f" ]] && ! [[ "$FORCE" == true && "${3:-}" == rotatable ]]; then return; fi
  printf '%s' "$2" > "$f"
  echo "  wrote $f"
}

DB_NAME="${POSTGRES_DB:-aipulse}"
APP_USER="${APP_DB_USER:-aipulse}"
put postgres_password "$(rand 40)"
put app_db_password "$(rand 40)"
put metrics_db_password "$(rand 40)"
put redis_password "$(rand 40)" rotatable
put jwt_secret "$(rand 64)" rotatable
put metrics_token "$(rand 48)" rotatable
put grafana_admin_password "$(rand 24)"

# Derived connection strings (regenerated whenever their passwords change).
app_pw="$(cat "$DIR/app_db_password")"
redis_pw="$(cat "$DIR/redis_password")"
printf 'postgresql+asyncpg://%s:%s@postgres:5432/%s' "$APP_USER" "$app_pw" "$DB_NAME" > "$DIR/database_url"
printf 'redis://:%s@redis:6379/0' "$redis_pw" > "$DIR/redis_url"
printf '{"redis://redis:6379": "%s"}' "$redis_pw" > "$DIR/redis_exporter_passwords.json"

# Optional: empty means "not configured".
for f in openai_api_key anthropic_api_key github_token nvd_api_key; do
  [[ -e "$DIR/$f" ]] || { : > "$DIR/$f"; echo "  created empty $DIR/$f (optional)"; }
done
[[ -e "$DIR/alert_webhook_url" ]] || {
  printf 'http://127.0.0.1:9/configure-alert-webhook' > "$DIR/alert_webhook_url"
  echo "  created $DIR/alert_webhook_url (placeholder: put your Slack/Teams/webhook URL here)"
}
# Compose (without Swarm) bind-mounts file secrets with their host permissions, and the containers run as
# non-root users (app 10001, postgres/redis 999, grafana 472, nobody), so the files must be world-readable.
# The directory itself is 700: other users on the host cannot reach the files.
chmod 644 "$DIR"/*
chmod 700 "$DIR"
echo "Secrets ready in ./$DIR (keep this directory out of version control and backups of the repo)."
