#!/usr/bin/env bash
# Jury run in one command: clone → .env from the example → docker compose up → /api/ready → scenario 1.
#
#   scripts/check-clean-clone.sh                # the current repo's committed HEAD
#   scripts/check-clean-clone.sh <git url|path> [ref]
#
# Needs only git, bash and Docker with Compose v2. Runs in a temporary directory under its own
# compose project and ports (WEB_PORT 18080, BACKEND_PORT 18000 by default), so a running dev
# stack is not touched. Everything is removed at the end; KEEP=1 leaves the stack running.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_repo="${1:-$here}"
ref="${2:-}"
project="alfa-clean-$$"
web_port="${WEB_PORT:-18080}"
backend_port="${BACKEND_PORT:-18000}"
work="$(mktemp -d)"
started=$(date +%s)

log() { printf '\n== %s\n' "$*"; }

cleanup() {
  status=$?
  if [ "${KEEP:-0}" = "1" ]; then
    log "KEEP=1: stack $project stays up — http://localhost:$web_port (folder $work/repo)"
    exit "$status"
  fi
  if [ -f "$work/repo/docker-compose.yml" ]; then
    if [ "$status" -ne 0 ]; then
      log "backend and init logs (last 60 lines)"
      (cd "$work/repo" && docker compose -p "$project" logs --tail 60 init backend) || true
    fi
    (cd "$work/repo" && docker compose -p "$project" down -v --remove-orphans >/dev/null 2>&1) || true
  fi
  rm -rf "$work" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT

log "clone $source_repo ${ref:+($ref)}"
git clone --quiet --no-local "$source_repo" "$work/repo"
cd "$work/repo"
if [ -n "$ref" ]; then git checkout --quiet "$ref"; fi
git log -1 --format='commit %h — %s'

log "configure: .env from .env.example, ports $web_port (web) and $backend_port (backend)"
cp .env.example .env
sed -i.bak "s/^WEB_PORT=.*/WEB_PORT=$web_port/" .env && rm -f .env.bak
printf 'BACKEND_PORT=%s\n' "$backend_port" >> .env

log "build and start: db → init (migrate, seed) → backend → swagger → web"
docker compose -p "$project" up -d --build --wait --wait-timeout 600
docker compose -p "$project" ps --format 'table {{.Service}}\t{{.Status}}'

log "scenario 1 through Caddy (inside the backend container: no Python or jq needed here)"
docker compose -p "$project" exec -T backend python - < scripts/smoke_scenario_1.py

log "clean clone OK in $(( $(date +%s) - started )) s — cabinet: http://localhost:$web_port"
