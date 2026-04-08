#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/prod-encar"
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
sudo id -u prod-encar >/dev/null 2>&1 || sudo useradd --system --home-dir "${APP_DIR}" --shell /usr/sbin/nologin prod-encar
sudo chown -R prod-encar:prod-encar "${APP_DIR}"
sudo cp "${APP_DIR}/deploy/systemd/prod-encar-api.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-encar-auto-update.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-encar-auto-update.timer" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-dongchedi-update.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-dongchedi-update.timer" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-encar-meilisearch-sync.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-encar-meilisearch-sync.timer" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-encar-subscriptions-notify.service" /etc/systemd/system/
sudo cp "${APP_DIR}/deploy/systemd/prod-encar-subscriptions-notify.timer" /etc/systemd/system/
sudo chmod +x "${APP_DIR}/deploy/scripts/run_meilisearch_sync_host.sh"

echo "[4/6] Install nginx site"
sudo cp "${APP_DIR}/deploy/nginx/prod-encar.conf" /etc/nginx/sites-available/prod-encar.conf
sudo ln -sf /etc/nginx/sites-available/prod-encar.conf /etc/nginx/sites-enabled/prod-encar.conf
sudo nginx -t

echo "[5/6] Reload daemons"
sudo systemctl daemon-reload
sudo systemctl enable --now prod-encar-api.service
sudo systemctl enable --now prod-encar-auto-update.timer
sudo systemctl enable --now prod-dongchedi-update.timer
sudo systemctl enable --now prod-encar-meilisearch-sync.timer
sudo systemctl enable --now prod-encar-subscriptions-notify.timer
sudo systemctl reload nginx

echo "[6/6] Health check"
curl -fsS http://127.0.0.1/api/health || true
echo "Done."
