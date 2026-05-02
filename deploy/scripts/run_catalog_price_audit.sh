#!/usr/bin/env bash
# Запуск deploy/scripts/catalog_price_coverage.sql внутри контейнера postgres.
# Обязательно передаём -U/-d: иначе psql внутри exec пытается зайти как root → FATAL: role "root" does not exist
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
cd "$ROOT"

POSTGRES_USER="${POSTGRES_USER:-wra}"
POSTGRES_DB="${POSTGRES_DB:-wra}"
SQL="${ROOT}/deploy/scripts/catalog_price_coverage.sql"

if docker compose version &>/dev/null; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose &>/dev/null; then
  DOCKER_COMPOSE=(docker-compose)
else
  echo "ERROR: need 'docker compose' (v2) or docker-compose (v1)" >&2
  exit 1
fi

if [[ ! -f "$SQL" ]]; then
  echo "ERROR: file not found: $SQL (git pull origin main)" >&2
  exit 1
fi

cat "$SQL" | "${DOCKER_COMPOSE[@]}" exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1
