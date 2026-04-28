#!/usr/bin/env bash
# Единый ночной Encar-каталог для rideauto: только rideauto-auto-update.{service,timer}.
# Снимает устаревшие encar-update.* (дубликат того же encar_daily_update), копирует актуальные юниты, reload.
#
#   sudo bash /opt/rideauto/deploy/scripts/rideauto_catalog_install.sh
#
# Переменные: WRA_REPO_ROOT=/opt/rideauto
set -euo pipefail
ROOT="${WRA_REPO_ROOT:-/opt/rideauto}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root: sudo bash $0" >&2
  exit 1
fi

echo "== legacy encar-update (если был) — stop / disable / unit files =="
systemctl stop encar-update.timer 2>/dev/null || true
systemctl stop encar-update.service 2>/dev/null || true
systemctl disable encar-update.timer 2>/dev/null || true
systemctl disable encar-update.service 2>/dev/null || true
rm -f /etc/systemd/system/encar-update.timer /etc/systemd/system/encar-update.service

echo "== install rideauto-auto-update =="
install -m 644 "${ROOT}/deploy/systemd/rideauto-auto-update.service" /etc/systemd/system/rideauto-auto-update.service
install -m 644 "${ROOT}/deploy/systemd/rideauto-auto-update.timer" /etc/systemd/system/rideauto-auto-update.timer

chmod +x "${ROOT}/deploy/scripts/run_encar_daily_once_prod.sh" 2>/dev/null || true
chmod +x "${ROOT}/deploy/scripts/encar_pull_kill_start.sh" 2>/dev/null || true
chmod +x "${ROOT}/deploy/scripts/encar_set_proxy_urls.sh" 2>/dev/null || true
chmod +x "${ROOT}/deploy/scripts/rideauto_catalog_install.sh" 2>/dev/null || true
chmod +x "${ROOT}/deploy/scripts/run_postgres_catalog_sync_host.sh" 2>/dev/null || true
chmod +x "${ROOT}/deploy/scripts/rideauto_git_pull.sh" 2>/dev/null || true

systemctl daemon-reload
systemctl enable rideauto-auto-update.timer
systemctl start rideauto-auto-update.timer

echo "OK. Ночной Encar: rideauto-auto-update.timer → rideauto-auto-update.service"
systemctl status rideauto-auto-update.timer --no-pager -l || true
