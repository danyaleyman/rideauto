#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/rideauto"
REPO_SRC="${1:-$(pwd)}"

echo "[1/6] Sync project to ${APP_DIR}"
sudo mkdir -p "${APP_DIR}"
sudo rsync -a --delete --exclude ".git" --exclude "node_modules" "${REPO_SRC}/" "${APP_DIR}/"

echo "[2/6] Install Python dependencies"
if [ -f "${APP_DIR}/backend/requirements.txt" ]; then
  sudo python3 -m pip install -r "${APP_DIR}/backend/requirements.txt"
fi
sudo python3 -m pip install aiohttp

echo "[3/6] Install systemd units"
sudo id -u rideauto >/dev/null 2>&1 || sudo useradd --system --home-dir "${APP_DIR}" --shell /usr/sbin/nologin rideauto
sudo chown -R rideauto:rideauto "${APP_DIR}"
sudo cp "${APP_DIR}/deploy/systemd/rideauto-api.service" /etc/systemd/system/
sudo chmod +x "${APP_DIR}/deploy/scripts/rideauto_catalog_install.sh"
sudo bash "${APP_DIR}/deploy/scripts/rideauto_catalog_install.sh"
sudo cp "${APP_DIR}/deploy/systemd/prod-dongchedi-update.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-dongchedi-update.timer" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/rideauto-meilisearch-sync.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/rideauto-meilisearch-sync.timer" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/rideauto-subscriptions-notify.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/rideauto-subscriptions-notify.timer" /etc/systemd/system/
sudo chmod +x "${APP_DIR}/deploy/scripts/run_meilisearch_sync_host.sh"

echo "[4/6] Install nginx site"
sudo cp "${APP_DIR}/deploy/nginx/rideauto.conf" /etc/nginx/sites-available/rideauto.conf
sudo ln -sf /etc/nginx/sites-available/rideauto.conf /etc/nginx/sites-enabled/rideauto.conf
sudo nginx -t

echo "[5/6] Reload daemons"
sudo systemctl daemon-reload
sudo systemctl enable --now rideauto-api.service
sudo systemctl enable --now rideauto-auto-update.timer
sudo systemctl enable --now prod-dongchedi-update.timer
sudo systemctl enable --now rideauto-meilisearch-sync.timer
sudo systemctl enable --now rideauto-subscriptions-notify.timer
sudo systemctl reload nginx

echo "[6/6] Health check"
curl -fsS http://127.0.0.1/api/health || true
echo "Done."
