#!/usr/bin/env bash
# One-command production orchestration for rideauto.
# Runs the standard deploy pipeline on host:
#   1) git pull
#   2) install/refresh rideauto catalog systemd units
#   3) ensure runtime permissions
#   4) run one daily Encar cycle
#   5) postgres catalog sync
#   6) meilisearch sync
#   7) basic health checks
#
# Usage:
#   sudo bash /opt/rideauto/deploy/scripts/run_full_deploy_pipeline.sh
# Optional flags:
#   --skip-git-pull
#   --skip-daily
#   --skip-postgres-sync
#   --skip-meili-sync
#   --skip-health-check
set -euo pipefail

ROOT="${WRA_REPO_ROOT:-/opt/rideauto}"
RUNTIME_USER="${WRA_RUNTIME_USER:-rideauto}"
RUNTIME_GROUP="${WRA_RUNTIME_GROUP:-rideauto}"

SKIP_GIT_PULL=0
SKIP_DAILY=0
SKIP_PG_SYNC=0
SKIP_MEILI_SYNC=0
SKIP_HEALTH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-git-pull) SKIP_GIT_PULL=1 ;;
    --skip-daily) SKIP_DAILY=1 ;;
    --skip-postgres-sync) SKIP_PG_SYNC=1 ;;
    --skip-meili-sync) SKIP_MEILI_SYNC=1 ;;
    --skip-health-check) SKIP_HEALTH=1 ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

run_as_runtime_user() {
  local cmd="$1"
  su -s /bin/bash -c "$cmd" "$RUNTIME_USER"
}

echo "== rideauto full deploy pipeline =="
echo "ROOT=$ROOT"
echo "RUNTIME_USER=$RUNTIME_USER"

if [[ $SKIP_GIT_PULL -eq 0 ]]; then
  echo "== [1/7] git pull =="
  bash "$ROOT/deploy/scripts/rideauto_git_pull.sh"
else
  echo "== [1/7] git pull skipped =="
fi

echo "== [2/7] install/refresh rideauto catalog units =="
bash "$ROOT/deploy/scripts/rideauto_catalog_install.sh"

echo "== [3/7] ensure runtime permissions =="
WRA_RUNTIME_USER="$RUNTIME_USER" WRA_RUNTIME_GROUP="$RUNTIME_GROUP" bash "$ROOT/deploy/scripts/ensure_scraper_runtime_permissions.sh"

if [[ $SKIP_DAILY -eq 0 ]]; then
  echo "== [4/7] run one daily cycle =="
  run_as_runtime_user "$ROOT/deploy/scripts/run_encar_daily_once_prod.sh"
else
  echo "== [4/7] daily cycle skipped =="
fi

if [[ $SKIP_PG_SYNC -eq 0 ]]; then
  echo "== [5/7] postgres catalog sync =="
  run_as_runtime_user "$ROOT/deploy/scripts/run_postgres_catalog_sync_host.sh --no-meilisearch"
else
  echo "== [5/7] postgres catalog sync skipped =="
fi

if [[ $SKIP_MEILI_SYNC -eq 0 ]]; then
  echo "== [6/7] meilisearch sync =="
  bash "$ROOT/deploy/scripts/run_meilisearch_sync_host.sh"
else
  echo "== [6/7] meilisearch sync skipped =="
fi

if [[ $SKIP_HEALTH -eq 0 ]]; then
  echo "== [7/7] health checks =="
  curl -fsS "http://127.0.0.1:8080/api/health" >/dev/null
  curl -fsS "http://127.0.0.1:8080/metrics" >/dev/null || true
  systemctl status rideauto-api.service --no-pager -l >/dev/null
  systemctl status rideauto-auto-update.timer --no-pager -l >/dev/null
  echo "Health checks: OK"
else
  echo "== [7/7] health checks skipped =="
fi

echo "== full deploy pipeline completed =="
