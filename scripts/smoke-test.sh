#!/usr/bin/env bash
# End-to-end smoke test of a running Compose stack, through the public web entrypoint.
#   scripts/smoke-test.sh [base-url]        (default http://localhost:<port Docker publishes for web>, else
#                                            WEB_PORT from the environment or .env, else 3000; https://<DOMAIN>
#                                            with the edge)
# Checks: web serves pages, the API answers through the same-origin rewrite, auth round trip (register,
# login, refresh cookie, /me), rate limiting answers 429, security headers, /metrics is not public,
# and (inside the stack) every container is healthy, runs as non-root with a read-only root filesystem.
set -euo pipefail
cd "$(dirname "$0")/.."
read -r -a COMPOSE_EXTRA <<< "${COMPOSE_FILES:-}"  # e.g. "-f docker-compose.yml -f docker-compose.prod.yml"
COMPOSE=(docker compose "${COMPOSE_EXTRA[@]}")
# The web port: the one Docker actually publishes for the running web container (whatever .env or an
# override file says), else WEB_PORT from the environment or .env, else 3000.
web_port="$("${COMPOSE[@]}" port web 3000 2>/dev/null | tail -1 | sed -n 's/.*:\([0-9][0-9]*\)[[:space:]]*$/\1/p' || true)"
if [[ -z "$web_port" ]]; then
  web_port="${WEB_PORT:-$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}WEB_PORT[[:space:]]*=[[:space:]]*["'"'"']\{0,1\}\([0-9][0-9]*\).*/\2/p' .env 2>/dev/null | tail -1)}"
fi
BASE="${1:-http://localhost:${web_port:-3000}}"
EMAIL="smoke-$(date +%s)-$RANDOM@example.com"
PASS="Smoke-test-Passw0rd!"
JAR="$(mktemp)"
trap 'rm -f "$JAR" "$JAR.h"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
# Extra curl options, e.g. SMOKE_CURL_OPTS=--insecure for Caddy's local CA on https://localhost
read -r -a CURL_EXTRA <<< "${SMOKE_CURL_OPTS:-}"
curl() { command curl "${CURL_EXTRA[@]}" "$@"; }
ok() { echo "ok   $*"; }

# The browser tests (scripts/e2e.sh) leave the stack running with relaxed rate limits on purpose, and the
# rate-limit check below would then fail for that reason alone: say so instead.
api_id="$("${COMPOSE[@]}" ps -q api 2>/dev/null | head -1 || true)"
if [[ -n "$api_id" ]] && docker inspect "$api_id" --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' 2>/dev/null | grep -q 'docker-compose.e2e.yml'; then
  fail "the stack runs with the e2e test settings (relaxed rate limits). Restart it normally first: docker compose up -d --wait (or use ./scripts/check.sh smoke, which does it)"
fi

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

# POST JSON to an auth endpoint and print "<body>\n<status>". The smoke test itself exhausts the auth rate
# limit (see the 429 check below), so a second run within the same minute waits for Retry-After instead of
# failing: at most 3 waits of at most 65 s each.
auth_post() {  # auth_post <path> <json> [extra curl args...]
  local path="$1" data="$2" out status wait tries=0
  shift 2
  while :; do
    out="$(curl -s -D "$JAR.h" -w '\n%{http_code}' -H 'content-type: application/json' -d "$data" "$@" "$BASE$path")"
    status="${out##*$'\n'}"
    if [[ "$status" != 429 || $tries -ge 3 ]]; then printf '%s' "$out"; return; fi
    wait="$(awk 'tolower($1)=="retry-after:"{print $2+0}' "$JAR.h" | tr -d '\r')"
    wait="${wait:-5}"; ((wait > 65)) && wait=65
    tries=$((tries + 1))
    echo "wait auth rate limit window: ${wait}s" >&2
    sleep "$((wait + 1))"
  done
}

status="$(code "$BASE/login")" || true  # curl fails (000) when nothing listens
[[ "$status" == 200 ]] || fail "web /login answered $status at $BASE (is the stack running on this port? WEB_PORT in .env)"
ok "web serves /login"
status="$(code "$BASE/api/v1/categories")" || true
[[ "$status" == 200 ]] || fail "API through the web rewrite: $BASE/api/v1/categories answered $status (another program on this port? WEB_PORT in .env; else docker compose logs --tail 50 api web)"
ok "API reachable through the web origin"

hdrs="$(curl -s -D - -o /dev/null "$BASE/api/v1/categories")"
grep -qi '^x-content-type-options: nosniff' <<<"$hdrs" || fail "missing nosniff header"
grep -qi '^cache-control: no-store' <<<"$hdrs" || fail "API responses must not be cached"
ok "security headers"

r="$(auth_post /api/v1/auth/register "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")"
[[ "${r##*$'\n'}" == 201 ]] || fail "register: $r"
ok "register"
r="$(auth_post /api/v1/auth/login "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" -c "$JAR")"
[[ "${r##*$'\n'}" == 200 ]] || fail "login: $r"
token="$(sed -n '1p' <<<"$r" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
grep -q aipulse_refresh "$JAR" || fail "refresh cookie not set"
grep -E 'aipulse_refresh' "$JAR" | grep -q '#HttpOnly_' || fail "refresh cookie must be HttpOnly"
ok "login sets an HttpOnly refresh cookie"
[[ "$(code -H "Authorization: Bearer $token" "$BASE/api/v1/auth/me")" == 200 ]] || fail "/me"
[[ "$(code "$BASE/api/v1/auth/me")" == 401 ]] || fail "/me without token must be 401"
ok "authenticated /me, anonymous 401"
[[ "$(code -H "Authorization: Bearer $token" "$BASE/api/v1/admin/system/health")" == 403 ]] || fail "admin route for a user"
ok "RBAC: admin routes refuse regular users"

limited=0
for _ in $(seq 1 15); do
  c="$(code -H 'content-type: application/json' -d '{"email":"nobody@example.com","password":"wrong-password-1"}' "$BASE/api/v1/auth/login")"
  [[ "$c" == 429 ]] && { limited=1; break; }
done
[[ "$limited" == 1 ]] || fail "login is not rate limited"
ok "login rate limited (429)"

[[ "$(code "$BASE/metrics")" != 200 ]] || fail "/metrics must not be public"
ok "/metrics not exposed on the web origin"

if command -v docker >/dev/null && "${COMPOSE[@]}" ps -q api >/dev/null 2>&1; then
  unhealthy="$("${COMPOSE[@]}" ps --format '{{.Service}} {{.Health}}' | awk '$2=="unhealthy"{print $1}')"
  [[ -z "$unhealthy" ]] || fail "unhealthy containers: $unhealthy"
  ok "no unhealthy containers"
  for svc in api worker beat web; do
    id="$("${COMPOSE[@]}" ps -q "$svc" | head -1)"
    [[ -n "$id" ]] || continue
    user="$(docker inspect -f '{{.Config.User}}' "$id")"
    ro="$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$id")"
    [[ -n "$user" && "$user" != root && "$user" != 0 && "$user" != "0:0" ]] || fail "$svc runs as root"
    [[ "$ro" == true ]] || fail "$svc root filesystem is writable"
  done
  ok "api/worker/beat/web: non-root, read-only root filesystem"
  "${COMPOSE[@]}" exec -T api python -c "
import urllib.request, os
t = open('/run/secrets/metrics_token').read().strip()
r = urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/metrics', headers={'Authorization': 'Bearer ' + t}))
body = r.read().decode()
for m in ('aipulse_dependency_up{name=\"postgres\"} 1.0', 'aipulse_dependency_up{name=\"redis\"} 1.0', 'aipulse_celery_queue_length'):
    assert m in body, m
" || fail "metrics with token"
  ok "metrics (with token) report postgres and redis up"
fi
echo "Smoke test passed against $BASE"
