#!/usr/bin/env bash
# На VPS: правка .env под compose + пересборка api/web.
# Запуск: cd /opt/rideauto && bash deploy/scripts/server_compose_env_fix_and_deploy.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "=== git pull ==="
git pull

echo "=== fix .env (compose hostnames) ==="
python3 deploy/scripts/fix_compose_env.py

echo "=== build & start api ==="
docker compose build api
docker compose up -d --force-recreate api

echo "=== wait api healthy (up to 4 min) ==="
for i in $(seq 1 48); do
  if docker compose ps api 2>/dev/null | grep -q "(healthy)"; then
    echo "api is healthy"
    break
  fi
  if [ "$i" -eq 48 ]; then
    echo "api not healthy — logs:"
    docker compose logs api --tail=60
    exit 1
  fi
  sleep 5
done

echo "=== deploy web ==="
docker compose build web
docker compose up -d --no-deps web

echo "=== status ==="
docker compose ps
curl -sf http://127.0.0.1:8080/api/health | head -c 200 || true
echo ""
echo "Done."
