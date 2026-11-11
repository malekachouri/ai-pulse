#!/usr/bin/env bash
# Offsite copies of the database backups on S3-compatible storage (AWS S3, Cloudflare R2, Backblaze B2,
# Wasabi, MinIO, Ceph, versitygw ...), encrypted on this host before upload.
#
#   offsite.sh upload <file.dump>   encrypt (OpenPGP, AES-256, passphrase) + upload, with the plain .sha256
#   offsite.sh prune                delete offsite copies older than BACKUP_OFFSITE_RETENTION_DAYS
#   offsite.sh list                 "<key> <last-modified>" per offsite backup, oldest first
#   offsite.sh latest               name of the newest offsite backup (e.g. aipulse-20260101T000000Z.dump)
#   offsite.sh fetch <name|latest>  decrypted dump on stdout (its checksum: `offsite.sh fetch-sum <name>`)
#   offsite.sh init                 create the bucket if it does not exist (self-hosted S3 servers)
#   offsite.sh enabled              exit 0 when offsite copies are configured
#
# Configuration (environment): BACKUP_S3_ENDPOINT (https://...), BACKUP_S3_BUCKET, BACKUP_S3_REGION
# (default us-east-1), BACKUP_S3_PREFIX (default "ai-pulse/"), BACKUP_OFFSITE_RETENTION_DAYS (default 30).
# Credentials are Docker secrets (files), never environment variables:
#   /run/secrets/backup_s3_access_key_id, /run/secrets/backup_s3_secret_access_key,
#   /run/secrets/backup_encryption_passphrase  (keep a copy OUTSIDE this host: without it nothing restores)
# Requests are signed with AWS Signature V4 by curl; path-style URLs (<endpoint>/<bucket>/<key>).
set -euo pipefail
shopt -s inherit_errexit
umask 077

SECRETS="${BACKUP_SECRETS_DIR:-/run/secrets}"
ENDPOINT="${BACKUP_S3_ENDPOINT:-}"
BUCKET="${BACKUP_S3_BUCKET:-}"
REGION="${BACKUP_S3_REGION:-us-east-1}"
PREFIX="${BACKUP_S3_PREFIX-ai-pulse/}"
RETENTION_DAYS="${BACKUP_OFFSITE_RETENTION_DAYS:-30}"
export GNUPGHOME="${GNUPGHOME:-/tmp/.gnupg}"

die() { echo "{\"event\":\"offsite_error\",\"detail\":\"$*\"}" >&2; exit 1; }
secret() { [[ -s "$SECRETS/$1" ]] || die "missing secret $1"; tr -d '\r\n' < "$SECRETS/$1"; }

enabled() { [[ -n "$ENDPOINT" && -n "$BUCKET" ]]; }

check_config() {
  enabled || die "offsite backups are not configured (BACKUP_S3_ENDPOINT / BACKUP_S3_BUCKET)"
  [[ "$ENDPOINT" =~ ^https?://[A-Za-z0-9.:-]+/?$ ]] || die "BACKUP_S3_ENDPOINT must be a URL like https://s3.example.com"
  [[ "$BUCKET" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || die "invalid bucket name"
  [[ "$PREFIX" =~ ^[A-Za-z0-9._/-]*$ ]] || die "BACKUP_S3_PREFIX may contain only letters, digits, . _ / -"
  [[ "$RETENTION_DAYS" =~ ^[0-9]+$ && "$RETENTION_DAYS" -ge 1 ]] || die "BACKUP_OFFSITE_RETENTION_DAYS must be >= 1"
  for f in backup_s3_access_key_id backup_s3_secret_access_key backup_encryption_passphrase; do
    [[ -s "$SECRETS/$f" ]] || die "missing secret $f (scripts/generate-secrets.sh, docs/DEPLOYMENT.md section 5)"
  done
  mkdir -p "$GNUPGHOME"
}

# s3 <curl args...>: a signed request (the payload is not hashed into the signature: the OpenPGP
# encryption already protects the content's integrity, and large dumps are not read twice). Credentials reach curl through a config on a file descriptor, so
# they never appear in the process list.
s3() {
  local key secret_key
  key="$(secret backup_s3_access_key_id)"
  secret_key="$(secret backup_s3_secret_access_key)"
  curl --silent --show-error --fail --retry 3 --retry-delay 5 --connect-timeout 20 \
    --aws-sigv4 "aws:amz:${REGION}:s3" -H "x-amz-content-sha256: UNSIGNED-PAYLOAD" \
    -K <(printf 'user = "%s:%s"\n' "$key" "$secret_key") "$@"
}

url() { printf '%s/%s/%s' "${ENDPOINT%/}" "$BUCKET" "$1"; }

# AWS URI encoding (RFC 3986 unreserved characters kept). curl signs the query string as written, so it
# must already be canonical: encoded like this and with the parameters in alphabetical order.
uri_encode() {
  local s="$1" out="" c i
  for (( i = 0; i < ${#s}; i++ )); do
    c="${s:i:1}"
    case "$c" in
      [A-Za-z0-9._~-]) out+="$c" ;;
      *) out+="$(printf '%%%02X' "'$c")" ;;
    esac
  done
  printf '%s' "$out"
}

encrypt() {  # encrypt <in> <out>
  gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-fd 3 --no-symkey-cache --symmetric \
    --cipher-algo AES256 --s2k-digest-algo SHA512 --compress-algo none --output "$2" "$1" \
    3< <(secret backup_encryption_passphrase)
}

decrypt() {  # stdin -> stdout
  gpg --batch --quiet --pinentry-mode loopback --passphrase-fd 3 --no-symkey-cache --decrypt \
    3< <(secret backup_encryption_passphrase)
}

upload() {
  local file="$1" name enc
  [[ -f "$file" && -f "$file.sha256" ]] || die "upload needs $file and $file.sha256"
  name="$(basename "$file")"
  enc="$file.gpg.partial"
  # shellcheck disable=SC2064 # expand now: $enc is local to this function
  trap "rm -f '$enc'" EXIT
  encrypt "$file" "$enc"
  s3 -T "$enc" -H "Content-Type: application/octet-stream" "$(url "${PREFIX}${name}.gpg")" > /dev/null
  rm -f "$enc"
  # The checksum of the plain dump (not sensitive), uploaded last: its presence marks a complete copy.
  s3 -T "$file.sha256" -H "Content-Type: text/plain" "$(url "${PREFIX}${name}.sha256")" > /dev/null
  echo "{\"event\":\"offsite_ok\",\"key\":\"${PREFIX}${name}.gpg\",\"bytes\":$(stat -c %s "$file")}"
}

# "<key> <LastModified>" for every object under the prefix (ListObjectsV2, paginated).
objects() {
  local token="" page
  while :; do
    local query
    query="list-type=2&prefix=$(uri_encode "$PREFIX")"
    [[ -n "$token" ]] && query="continuation-token=$(uri_encode "$token")&${query}"
    page="$(s3 "${ENDPOINT%/}/${BUCKET}?${query}")"
    printf '%s' "$page" | tr -d '\n' | sed 's#</Contents>#\n#g' \
      | sed -n 's#.*<Key>\([^<]*\)</Key>.*<LastModified>\([^<]*\)</LastModified>.*#\1 \2#p;
                s#.*<LastModified>\([^<]*\)</LastModified>.*<Key>\([^<]*\)</Key>.*#\2 \1#p'
    grep -q '<IsTruncated>true</IsTruncated>' <<< "$page" || break
    token="$(sed -n 's#.*<NextContinuationToken>\([^<]*\)</NextContinuationToken>.*#\1#p' <<< "$page")"
    [[ -n "$token" ]] || break
  done
}

list() {
  local all
  all="$(objects)"
  grep '\.dump\.gpg ' <<< "$all" | sort || true
}

latest() {
  local all key
  all="$(objects)"
  key="$(awk '{print $1}' <<< "$all" | grep '\.dump\.sha256$' | sort | tail -1 || true)"  # complete copies
  [[ -n "$key" ]] || die "no offsite backup found under ${PREFIX}"
  basename "${key%.sha256}"
}

resolve() { if [[ "${1:-latest}" == latest ]]; then latest; else basename "$1"; fi; }

fetch() {
  local name
  name="$(resolve "${1:-latest}")"
  [[ "$name" =~ ^[A-Za-z0-9._-]+\.dump$ ]] || die "invalid backup name: $name"
  s3 "$(url "${PREFIX}${name}.gpg")" | decrypt
}

fetch_sum() {
  local name
  name="$(resolve "${1:-latest}")"
  s3 "$(url "${PREFIX}${name}.sha256")"
}

prune() {
  local all cutoff deleted=0 key modified
  all="$(objects)"
  cutoff=$(( $(date -u +%s) - RETENTION_DAYS * 86400 ))
  while read -r key modified; do
    [[ -n "$key" ]] || continue
    if [[ "$(date -u -d "$modified" +%s)" -lt "$cutoff" ]]; then
      s3 -X DELETE "$(url "$key")" > /dev/null
      deleted=$((deleted + 1))
    fi
  done < <(grep -E '\.dump\.(gpg|sha256) ' <<< "$all" || true)
  echo "{\"event\":\"offsite_pruned\",\"deleted\":$deleted,\"retention_days\":$RETENTION_DAYS}"
}

init() {
  if s3 -o /dev/null -I "${ENDPOINT%/}/${BUCKET}" 2>/dev/null; then return 0; fi
  s3 -X PUT "${ENDPOINT%/}/${BUCKET}" > /dev/null
  echo "{\"event\":\"offsite_bucket_created\",\"bucket\":\"$BUCKET\"}"
}

cmd="${1:-}"
shift || true
case "$cmd" in
  enabled) enabled ;;
  upload) check_config; upload "${1:?file}" ;;
  prune) check_config; prune ;;
  list) check_config; list ;;
  latest) check_config; latest ;;
  fetch) check_config; fetch "${1:-latest}" ;;
  fetch-sum) check_config; fetch_sum "${1:-latest}" ;;
  init) check_config; init ;;
  *) sed -n '2,17p' "$0" >&2; exit 2 ;;
esac
