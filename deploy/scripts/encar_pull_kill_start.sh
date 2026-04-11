#!/usr/bin/env bash
# Полный цикл на VPS: остановить таймер/сервис, убить залипшие encar-процессы, git pull, одноразовый daily.
# Запуск от root:
#   sudo bash /opt/prod-encar/deploy/scripts/encar_pull_kill_start.sh
#
# Переменные (опционально):
#   WRA_REPO_ROOT=/opt/prod-encar  WRA_RUNTIME_USER=prod-encar
set -euo pipefail
ROOT="${WRA_REPO_ROOT:-/opt/prod-encar}"
RUN_USER="${WRA_RUNTIME_USER:-prod-encar}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root: sudo bash $0" >&2
  exit 1
fi

echo "== systemd: стоп (если юниты есть) =="
systemctl stop prod-encar-auto-update.service 2>/dev/null || true
systemctl stop prod-encar-auto-update.timer 2>/dev/null || true
systemctl stop encar-update.service 2>/dev/null || true
systemctl stop encar-update.timer 2>/dev/null || true

echo "== pkill: encar_scraper / encar_daily_update от ${RUN_USER} =="
# Только процессы пользователя сервиса и только пути из этого репо
pkill -u "${RUN_USER}" -f "${ROOT}/backend/encar_scraper.py" 2>/dev/null || true
pkill -u "${RUN_USER}" -f "${ROOT}/backend/encar_daily_update.py" 2>/dev/null || true
sleep 2

echo "== git pull =="
if ! sudo -u "${RUN_USER}" -H bash -lc "cd \"${ROOT}\" && git pull origin main"; then
  echo "git pull failed. Если dubious ownership: sudo -u ${RUN_USER} -H git config --global --add safe.directory ${ROOT}" >&2
  exit 1
fi

echo "== encar_daily_update --once =="
sudo -u "${RUN_USER}" "${ROOT}/deploy/scripts/run_encar_daily_once_prod.sh"

echo "OK. Таймер снова: sudo systemctl start prod-encar-auto-update.timer (или ваш encar-update.timer)."
