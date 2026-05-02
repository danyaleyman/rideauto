#!/usr/bin/env bash
# Интерактивный сброс каталога + Encar checkpoint в Postgres (см. pg_reset_encar_catalog.sql).
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
cd "$ROOT"

POSTGRES_USER="${POSTGRES_USER:-wra}"
POSTGRES_DB="${POSTGRES_DB:-wra}"
SQL="${ROOT}/deploy/scripts/pg_reset_encar_catalog.sql"

if docker compose version &>/dev/null; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose &>/dev/null; then
  DOCKER_COMPOSE=(docker-compose)
else
  echo "ERROR: need docker compose or docker-compose" >&2
  exit 1
fi

if [[ ! -f "$SQL" ]]; then
  echo "ERROR: missing $SQL" >&2
  exit 1
fi

cat "$SQL" | "${DOCKER_COMPOSE[@]}" exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1
