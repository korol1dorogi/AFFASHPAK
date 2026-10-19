#!/usr/bin/env bash
# Deploy the latest origin/main on the VPS; roll back to the previous commit if it fails.
# Installed as /usr/local/bin/alfa-deploy (docs/deploy.md). CI reaches it through an SSH key
# restricted with command="/usr/local/bin/alfa-deploy", so the caller cannot choose what runs.
# Note: rollback restores code only; database migrations are not reversed.
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/srv/alfa-cabinet}"
LOG_FILE="${LOG_FILE:-/var/log/alfa-deploy.log}"
LOCK_FILE=/var/lock/alfa-deploy.lock

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

previous="$(git rev-parse HEAD)"
git fetch --quiet origin main
target="$(git rev-parse origin/main)"

if [[ "$previous" == "$target" ]]; then
  log "already at ${target:0:7}, nothing to deploy"
  exit 0
fi

log "deploying ${previous:0:7} -> ${target:0:7}"
git reset --hard --quiet "$target"

if up; then
  log "ok: ${target:0:7} is live"
  docker image prune -f >/dev/null
  exit 0
fi

log "FAILED: ${target:0:7}, rolling back to ${previous:0:7}"
git reset --hard --quiet "$previous"
if up; then
  log "rolled back to ${previous:0:7}"
else
  log "ROLLBACK FAILED: check 'docker compose ps' and 'docker compose logs'"
fi
exit 1
