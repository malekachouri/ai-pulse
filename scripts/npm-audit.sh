#!/usr/bin/env bash
# npm audit for one package directory (default: frontend).
#   1. Production dependencies: any moderate+ advisory fails, no exceptions.
#   2. All dependencies (development tools included): any moderate+ advisory fails, except advisories listed
#      in .github/npm-audit-allowlist that have not expired.
# Needs node_modules installed (npm ci) and jq.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${1:-frontend}"
ALLOW=.github/npm-audit-allowlist
TODAY="$(date -u +%F)"

echo "==> $DIR: production dependencies"
(cd "$DIR" && npm audit --omit=dev --audit-level=moderate)

echo "==> $DIR: all dependencies (allowlist: $ALLOW)"
declare -A allowed=()
if [[ -f "$ALLOW" ]]; then
  while read -r id expires reason; do
    [[ -z "$id" || "$id" == \#* ]] && continue
    if [[ "$expires" < "$TODAY" ]]; then
      echo "allowlist entry expired on $expires, not applied: $id ($reason)"
    else
      allowed[$id]="$expires $reason"
    fi
  done < "$ALLOW"
fi

json="$(cd "$DIR" && { npm audit --json 2>/dev/null || true; })"  # npm audit exits 1 when it finds anything
mapfile -t found < <(jq -r '.vulnerabilities // {} | .[] | .via[]? | objects
  | select(.severity == "moderate" or .severity == "high" or .severity == "critical")
  | "\(.url | split("/") | last) \(.severity) \(.name): \(.title)"' <<< "$json" | sort -u)

blocking=0
for line in "${found[@]}"; do
  id="${line%% *}"
  if [[ -n "${allowed[$id]:-}" ]]; then
    echo "accepted until ${allowed[$id]%% *}: $line"
  else
    echo "BLOCKING: $line"
    blocking=1
  fi
done
if [[ $blocking -eq 1 ]]; then
  echo "Fix the advisories above (npm update / a newer version), or, for development-only tooling with no fix," >&2
  echo "add them to $ALLOW with an expiry date and a reason." >&2
  exit 1
fi
echo "ok: no blocking advisories (${#found[@]} found, all accepted)"
