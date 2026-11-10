#!/bin/sh
# Starts redis-server with the password from REDIS_PASSWORD_FILE or REDIS_PASSWORD (never on the command line
# of a shell history; the config is written to a private tmpfs file).
set -eu
if [ -n "${REDIS_PASSWORD_FILE:-}" ]; then PASS="$(tr -d '\r\n' < "$REDIS_PASSWORD_FILE")"; else PASS="${REDIS_PASSWORD:-}"; fi
if [ -z "$PASS" ]; then echo "REDIS_PASSWORD(_FILE) is required" >&2; exit 1; fi
umask 077
CONF=/tmp/redis-auth.conf
printf 'include /usr/local/etc/redis/redis.conf\nrequirepass "%s"\n' "$PASS" > "$CONF"
exec redis-server "$CONF" "$@"
