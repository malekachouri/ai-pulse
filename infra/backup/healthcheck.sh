#!/usr/bin/env bash
# Healthy while the newest dump is younger than BACKUP_INTERVAL_SECONDS + 1 hour and, when offsite copies
# are configured, the last successful upload is as recent.
max_minutes=$(( ${BACKUP_INTERVAL_SECONDS:-86400} / 60 + 60 ))
newest=$(find /backups -name '*.dump' -mmin "-${max_minutes}" -print -quit)
[[ -n "$newest" ]] || exit 1
if bash /backup/offsite.sh enabled; then
  [[ -n "$(find /backups -maxdepth 1 -name .offsite-ok -mmin "-${max_minutes}" -print -quit)" ]] || exit 1
fi
