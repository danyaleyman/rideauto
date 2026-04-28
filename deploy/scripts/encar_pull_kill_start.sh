#!/usr/bin/env bash
# Полный цикл на VPS: остановить таймер/сервис, убить залипшие encar-процессы, git pull, одноразовый daily.
# Запуск от root:
#   sudo bash /opt/rideauto/deploy/scripts/encar_pull_kill_start.sh
#
# Переменные (опционально):
#   WRA_REPO_ROOT=/opt/rideauto  WRA_RUNTIME_USER=rideauto
set -euo pipefail
ROOT="${WRA_REPO_ROOT:-/opt/rideauto}"
RUN_USER="${WRA_RUNTIME_USER:-rideauto}"

if [[ ! -d "${ROOT}/.git" ]]; then
  echo "Не git-репозиторий: ${ROOT}/.git не найден" >&2
  exit 1
fi
ROOT="$(cd "${ROOT}" && pwd -P)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root: sudo bash $0" >&2
  exit 1
fi

echo "== systemd: стоп (если юниты есть) =="
systemctl stop rideauto-auto-update.service 2>/dev/null || true
systemctl stop rideauto-auto-update.timer 2>/dev/null || true

echo "== pkill: encar_scraper / encar_daily_update от ${RUN_USER} =="
# Только процессы пользователя сервиса и только пути из этого репо
pkill -u "${RUN_USER}" -f "${ROOT}/backend/encar_scraper.py" 2>/dev/null || true
pkill -u "${RUN_USER}" -f "${ROOT}/backend/encar_daily_update.py" 2>/dev/null || true
sleep 2

echo "== git: safe.directory (локально в репо, от root) =="
# Не трогаем ~/.gitconfig у rideauto (часто HOME=/opt/rideauto → Permission denied на .gitconfig в корне репо).
git -C "${ROOT}" config --local --get-all safe.directory 2>/dev/null | grep -Fxq "${ROOT}" 2>/dev/null || \
  git -C "${ROOT}" config --local --add safe.directory "${ROOT}" 2>/dev/null || true

echo "== git pull (от root) =="
if ! git -C "${ROOT}" pull origin main; then
  echo "git pull failed" >&2
  exit 1
fi

echo "== encar_daily_update --once =="
sudo -u "${RUN_USER}" "${ROOT}/deploy/scripts/run_encar_daily_once_prod.sh"

echo "OK. Таймер снова: sudo systemctl start rideauto-auto-update.timer"
