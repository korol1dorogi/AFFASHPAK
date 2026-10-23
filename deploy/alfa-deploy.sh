#!/usr/bin/env bash
# Deploy the latest origin/main on the VPS; roll back to the previous commit if it fails.
# Installed as /usr/local/bin/alfa-deploy (docs/deploy.md). CI reaches it through an SSH key
# restricted with command="/usr/local/bin/alfa-deploy", so the caller cannot choose what runs.
#
#   alfa-deploy           deploy (what CI runs)
#   alfa-deploy backup    only dump the database, e.g. before a demo
#
# Every deploy dumps the database first and does not start without the dump. A failed deploy
# whose commits changed migrations restores that dump before the old code comes back up: old
# code must not run on a new schema. The installed copy keeps itself in step with the repo.
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/srv/alfa-cabinet}"
LOG_FILE="${LOG_FILE:-/var/log/alfa-deploy.log}"
LOCK_FILE="${LOCK_FILE:-/var/lock/alfa-deploy.lock}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/alfa-cabinet}"
BACKUP_KEEP="${BACKUP_KEEP:-10}"
INSTALLED="${INSTALLED:-/usr/local/bin/alfa-deploy}"
SELF_IN_REPO=deploy/alfa-deploy.sh

mode="${1:-deploy}"
if [[ "$mode" != deploy && "$mode" != backup ]]; then
  echo "usage: alfa-deploy [backup]" >&2
  exit 2
fi

# A dropped SSH connection (cancelled CI job) must not kill a half-done deploy.
trap '' HUP

exec 9>"$LOCK_FILE"
if ! flock -w 900 9; then
  echo "another deploy is still running" >&2
  exit 1
fi
exec > >(tee -a "$LOG_FILE") 2>&1

log() { echo "[$(date -Is)] $*"; }

cd "$REPO_DIR"
domain="$(sed -n 's/^DOMAIN=//p' .env)"

healthy() {
  curl -fsS --max-time 10 --retry 12 --retry-delay 5 --retry-all-errors \
    --resolve "${domain}:443:127.0.0.1" "https://${domain}/api/health" >/dev/null
}

up() {
  docker compose up -d --build --wait --remove-orphans && healthy
}

# Dump the database to BACKUP_DIR/<label>-<time>-<commit>.sql.gz and print its path; keep the
# newest BACKUP_KEEP dumps of that label. A dump that did not finish is removed, not kept.
backup() {
  local label="$1" file
  install -d -m 700 "$BACKUP_DIR"
  file="$BACKUP_DIR/${label}-$(date +%Y%m%d-%H%M%S)-$(git rev-parse --short HEAD).sql.gz"
  if ! docker compose exec -T db sh -c \
    'pg_dump --clean --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip >"$file.part"; then
    rm -f "$file.part"
    return 1
  fi
  mv "$file.part" "$file"
  ls -1t "$BACKUP_DIR/${label}"-*.sql.gz | tail -n +$((BACKUP_KEEP + 1)) | xargs -r rm -f --
  echo "$file"
}

# The dump has DROP … IF EXISTS before every CREATE: it replaces the schema and the data.
restore() {
  docker compose stop backend worker
  gunzip -c "$1" | docker compose exec -T db sh -c \
    'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" "$POSTGRES_DB"' >/dev/null
}

# CI runs the installed copy: bring it in step with the repo for the next run. A rename, not
# an overwrite: bash is still reading this very file.
sync_self() {
  [[ -f "$SELF_IN_REPO" ]] || return 0
  if ! cmp -s "$SELF_IN_REPO" "$INSTALLED"; then
    install -m 755 "$SELF_IN_REPO" "$INSTALLED.new"
    mv -f "$INSTALLED.new" "$INSTALLED"
    log "updated $INSTALLED from $SELF_IN_REPO; the next run uses it"
  fi
}

if [[ "$mode" == backup ]]; then
  if ! dump="$(backup manual)"; then
    log "FAILED: database backup"
    exit 1
  fi
  log "backup: $dump"
  exit 0
fi

previous="$(git rev-parse HEAD)"
git fetch --quiet origin main
target="$(git rev-parse origin/main)"

if [[ "$previous" == "$target" ]]; then
  log "already at ${target:0:7}, nothing to deploy"
  sync_self
  exit 0
fi

if ! dump="$(backup predeploy)"; then
  log "FAILED: no database backup, ${target:0:7} not deployed"
  exit 1
fi
log "backup: $dump"

log "deploying ${previous:0:7} -> ${target:0:7}"
git reset --hard --quiet "$target"

if up; then
  log "ok: ${target:0:7} is live"
  docker image prune -f >/dev/null
  sync_self
  exit 0
fi

log "FAILED: ${target:0:7}, rolling back to ${previous:0:7}"
migrations="$(git diff --name-only "$previous" "$target" -- '*/migrations/*')"
git reset --hard --quiet "$previous"
if [[ -n "$migrations" ]]; then
  log "migrations changed, restoring the database from $dump"
  if ! restore "$dump"; then
    log "RESTORE FAILED: restore by hand from $dump (docs/deploy.md)"
  fi
fi
if up; then
  log "rolled back to ${previous:0:7}"
else
  log "ROLLBACK FAILED: check 'docker compose ps' and 'docker compose logs'"
fi
exit 1
