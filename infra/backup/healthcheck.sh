#!/usr/bin/env bash
# Healthy while the newest dump is younger than BACKUP_INTERVAL_SECONDS + 1 hour.
max_minutes=$(( ${BACKUP_INTERVAL_SECONDS:-86400} / 60 + 60 ))
newest=$(find /backups -name '*.dump' -mmin "-${max_minutes}" -print -quit)
[[ -n "$newest" ]]
