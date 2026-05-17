#!/usr/bin/env bash
# Быстрая диагностика и перезапуск API (compose).
set -euo pipefail
cd "$(dirname "$0")/../.."
echo "=== compose ps ==="
docker compose ps -a
echo "=== api logs (tail 80) ==="
docker compose logs api --tail=80
echo "=== restart api ==="
docker compose up -d api
echo "=== wait health (up to 3 min) ==="
for i in $(seq 1 36); do
  if docker compose ps api 2>/dev/null | grep -q "(healthy)"; then
    echo "api is healthy"
    exit 0
  fi
  sleep 5
done
echo "api still not healthy — check: docker compose logs api --tail=200"
echo "If Connection refused to Postgres: in .env use WRA_PG_DSN=@postgres:5432 (not 127.0.0.1) for compose api."
exit 1
