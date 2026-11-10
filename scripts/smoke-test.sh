#!/usr/bin/env bash
# End-to-end smoke test of a running Compose stack, through the public web entrypoint.
#   scripts/smoke-test.sh [base-url]        (default http://localhost:3000; https://<DOMAIN> with the edge)
# Checks: web serves pages, the API answers through the same-origin rewrite, auth round trip (register,
# login, refresh cookie, /me), rate limiting answers 429, security headers, /metrics is not public,
# and (inside the stack) every container is healthy, runs as non-root with a read-only root filesystem.
set -euo pipefail
BASE="${1:-http://localhost:3000}"
COMPOSE=(docker compose ${COMPOSE_FILES:-})
EMAIL="smoke-$(date +%s)-$RANDOM@example.com"
PASS="Smoke-test-Passw0rd!"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
# Extra curl options, e.g. SMOKE_CURL_OPTS=--insecure for Caddy's local CA on https://localhost
curl() { command curl ${SMOKE_CURL_OPTS:-} "$@"; }
ok() { echo "ok   $*"; }

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

[[ "$(code "$BASE/login")" == 200 ]] || fail "web /login"
ok "web serves /login"
[[ "$(code "$BASE/api/v1/categories")" == 200 ]] || fail "API through the web rewrite"
ok "API reachable through the web origin"

hdrs="$(curl -s -D - -o /dev/null "$BASE/api/v1/categories")"
grep -qi '^x-content-type-options: nosniff' <<<"$hdrs" || fail "missing nosniff header"
grep -qi '^cache-control: no-store' <<<"$hdrs" || fail "API responses must not be cached"
ok "security headers"

r="$(curl -s -w '\n%{http_code}' -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" "$BASE/api/v1/auth/register")"
[[ "${r##*$'\n'}" == 201 ]] || fail "register: $r"
ok "register"
r="$(curl -s -c "$JAR" -w '\n%{http_code}' -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" "$BASE/api/v1/auth/login")"
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
