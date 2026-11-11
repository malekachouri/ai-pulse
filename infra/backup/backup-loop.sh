#!/usr/bin/env bash
# Runs inside the "backup" service: a compressed, checksummed pg_dump every BACKUP_INTERVAL_SECONDS,
# keeping BACKUP_RETENTION_DAYS days locally. When BACKUP_S3_ENDPOINT/BUCKET are set, every dump is also
# encrypted and copied offsite (infrabash /backup/offsite.sh), with its own retention.
set -euo pipefail
umask 077
printf '%s:5432:*:%s:%s\n' "$PGHOST" "$PGUSER" "$(tr -d '\r\n' < "$PGPASSFILE_SOURCE")" > /tmp/.pgpass
export PGPASSFILE=/tmp/.pgpass
while true; do
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  out="/backups/${PGDATABASE}-${ts}.dump"
  if pg_dump --format=custom --compress=6 --no-owner --file="${out}.partial" "$PGDATABASE"; then
    mv "${out}.partial" "$out"
    # Relative name, so the checksum verifies wherever the pair is copied (restore.sh runs sha256sum -c).
    (cd /backups && sha256sum "$(basename "$out")" > "$(basename "$out").sha256")
    pg_restore --list "$out" > /dev/null   # the archive is readable
    echo "{\"event\":\"backup_ok\",\"file\":\"$(basename "$out")\",\"bytes\":$(stat -c %s "$out")}"
    if bash /backup/offsite.sh enabled; then
      # A failed upload never stops local backups; the healthcheck turns unhealthy instead.
      if bash /backup/offsite.sh upload "$out" && bash /backup/offsite.sh prune; then
        date -u +%s > /backups/.offsite-ok
      else
        rm -f "${out}.gpg.partial"
        echo "{\"event\":\"offsite_failed\",\"file\":\"$(basename "$out")\"}" >&2
      fi
    fi
  else
    rm -f "${out}.partial"
    echo "{\"event\":\"backup_failed\",\"time\":\"$ts\"}" >&2
  fi
  find /backups -name "${PGDATABASE}-*.dump*" -mtime +"${BACKUP_RETENTION_DAYS}" -delete
  sleep "$BACKUP_INTERVAL_SECONDS"
done
