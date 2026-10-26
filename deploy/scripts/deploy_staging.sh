#!/bin/bash
# Поднять/обновить только стейджинг. Прод web/api и скрейперы не трогает.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/rideauto}"
cd "${APP_DIR}"

echo "[staging] build api-stage web-stage"
docker compose --profile staging build api-stage web-stage

echo "[staging] up --no-deps (prod containers stay)"
docker compose --profile staging up -d --no-deps --force-recreate api-stage web-stage

if [ -f "${APP_DIR}/deploy/nginx/stage.rideauto.conf" ]; then
  cp "${APP_DIR}/deploy/nginx/stage.rideauto.conf" /etc/nginx/sites-available/stage.rideauto.conf
  ln -sf /etc/nginx/sites-available/stage.rideauto.conf /etc/nginx/sites-enabled/stage.rideauto.conf
  nginx -t
  systemctl reload nginx
fi

if command -v ufw >/dev/null 2>&1; then
  ufw status | grep -q inactive || ufw allow 8088/tcp || true
fi

echo "[staging] health"
curl -fsS -m 20 -H "Host: stage.rideauto.ru" http://127.0.0.1:8088/api/health || true
echo
docker compose --profile staging ps api-stage web-stage --format '{{.Name}} {{.Status}}'
echo "[staging] ready: http://stage.rideauto.ru  or  http://88.210.63.45:8088"
