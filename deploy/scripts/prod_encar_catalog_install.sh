#!/usr/bin/env bash
# Единый ночной Encar-каталог для rideauto: только prod-encar-auto-update.{service,timer}.
# Снимает устаревшие encar-update.* (дубликат того же encar_daily_update), копирует актуальные юниты, reload.
#
#   sudo bash /opt/prod-encar/deploy/scripts/prod_encar_catalog_install.sh
#
# Переменные: WRA_REPO_ROOT=/opt/prod-encar
set -euo pipefail
ROOT="${WRA_REPO_ROOT:-/opt/prod-encar}"

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

echo "== install prod-encar-auto-update =="
install -m 644 "${ROOT}/deploy/systemd/prod-encar-auto-update.service" /etc/systemd/system/prod-encar-auto-update.service
install -m 644 "${ROOT}/deploy/systemd/prod-encar-auto-update.timer" /etc/systemd/system/prod-encar-auto-update.timer

chmod +x "${ROOT}/deploy/scripts/run_encar_daily_once_prod.sh" 2>/dev/null || true
chmod +x "${ROOT}/deploy/scripts/encar_pull_kill_start.sh" 2>/dev/null || true
chmod +x "${ROOT}/deploy/scripts/encar_set_proxy_urls.sh" 2>/dev/null || true
chmod +x "${ROOT}/deploy/scripts/prod_encar_catalog_install.sh" 2>/dev/null || true

systemctl daemon-reload
systemctl enable prod-encar-auto-update.timer
systemctl start prod-encar-auto-update.timer

echo "OK. Ночной Encar: prod-encar-auto-update.timer → prod-encar-auto-update.service"
systemctl status prod-encar-auto-update.timer --no-pager -l || true
