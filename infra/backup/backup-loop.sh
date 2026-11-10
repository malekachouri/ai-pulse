#!/usr/bin/env bash
# Runs inside the "backup" service: a compressed, checksummed pg_dump every BACKUP_INTERVAL_SECONDS,
# keeping BACKUP_RETENTION_DAYS days. Copy /backups off the host (object storage) for disaster recovery.
set -euo pipefail
umask 077
printf '%s:5432:*:%s:%s\n' "$PGHOST" "$PGUSER" "$(tr -d '\r\n' < "$PGPASSFILE_SOURCE")" > /tmp/.pgpass
export PGPASSFILE=/tmp/.pgpass
while true; do
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  out="/backups/${PGDATABASE}-${ts}.dump"
  if pg_dump --format=custom --compress=6 --no-owner --file="${out}.partial" "$PGDATABASE"; then
    mv "${out}.partial" "$out"
    sha256sum "$out" > "${out}.sha256"
    pg_restore --list "$out" > /dev/null   # the archive is readable
    echo "{\"event\":\"backup_ok\",\"file\":\"$(basename "$out")\",\"bytes\":$(stat -c %s "$out")}"
  else
    rm -f "${out}.partial"
    echo "{\"event\":\"backup_failed\",\"time\":\"$ts\"}" >&2
  fi
  find /backups -name "${PGDATABASE}-*.dump*" -mtime +"${BACKUP_RETENTION_DAYS}" -delete
  sleep "$BACKUP_INTERVAL_SECONDS"
done
