#!/usr/bin/env bash
# git pull в /opt/rideauto от root: снимает типичную локальную правку скрипта, мешающую merge.
# Если правили другие файлы осознанно — сначала git stash -u (от root в репо).
set -euo pipefail
ROOT="${WRA_REPO_ROOT:-/opt/rideauto}"
cd "$ROOT"
if [[ ! -d .git ]]; then
  echo "rideauto_git_pull: нет .git в $ROOT" >&2
  exit 1
fi
if [[ "$(id -u)" -ne 0 ]]; then
  echo "rideauto_git_pull: запустите от root: sudo bash $0" >&2
  exit 1
fi

# Частый случай: chmod/правка только этого файла на сервере → pull не сливается.
git checkout -- deploy/scripts/run_postgres_catalog_sync_host.sh 2>/dev/null || true

git pull origin main
echo "OK: $ROOT на $(git rev-parse --short HEAD)"
