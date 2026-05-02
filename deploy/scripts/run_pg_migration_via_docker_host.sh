#!/usr/bin/env bash
# Применить SQL-миграцию к PostgreSQL через контейнер compose (postgres:16-alpine).
# На хосте Debian/Ubuntu без пакета postgresql-client локальный psql недоступен — используйте этот скрипт.
#
#   cd /opt/rideauto
#   bash deploy/scripts/run_pg_migration_via_docker_host.sh infrastructure/postgresql/migrations/006_encar_model_group_column.sql
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
MIG_REL_OR_ABS="${1:?usage: bash deploy/scripts/run_pg_migration_via_docker_host.sh <migration.sql>}"

cd "$ROOT"

if [[ -f .env ]]; then
  # shellcheck source=/dev/null
  set -a && source .env && set +a
fi

if [[ "${MIG_REL_OR_ABS}" == /* ]]; then
  MIG="$MIG_REL_OR_ABS"
else
  MIG="$ROOT/$MIG_REL_OR_ABS"
fi

if [[ ! -f "$MIG" ]]; then
  echo "migration file not found: $MIG" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  dc=(docker compose)
elif docker-compose version >/dev/null 2>&1; then
  dc=(docker-compose)
else
  echo "run_pg_migration_via_docker_host: need docker compose" >&2
  exit 1
fi

PU="${POSTGRES_USER:-wra}"
PD="${POSTGRES_DB:-wra}"

echo "run_pg_migration_via_docker_host: applying via container postgres psql …" >&2
"${dc[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$PU" -d "$PD" -f - <"$MIG"
echo "run_pg_migration_via_docker_host: ok — $MIG" >&2
