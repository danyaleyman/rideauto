#!/usr/bin/env bash
# Restore drill: восстановить дамп в ОТДЕЛЬНУЮ БД wra_restore_test (не трогает prod wra).
#
#   ./deploy/scripts/restore_pg_drill.sh [path/to/wra_YYYYMMDD.dump]
#   ./deploy/scripts/restore_pg_drill.sh   # использует backups/wra_latest.dump
#
# После успеха: миграции check + опционально drop test DB.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

DUMP="${1:-${BACKUP_FILE:-$ROOT/backups/wra_latest.dump}}"
TEST_DB="${RESTORE_TEST_DB:-wra_restore_test}"
POSTGRES_USER="${POSTGRES_USER:-wra}"

if [[ ! -f "$DUMP" ]]; then
  echo "restore_pg_drill: dump not found: $DUMP" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi

echo "restore_pg_drill: recreate database $TEST_DB …" >&2
"${DC[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TEST_DB' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS $TEST_DB;
CREATE DATABASE $TEST_DB OWNER $POSTGRES_USER;
SQL

echo "restore_pg_drill: pg_restore into $TEST_DB …" >&2
cat "$DUMP" | "${DC[@]}" exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$TEST_DB" --no-owner --no-privileges

export MIGRATE_DSN="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD:-wra}@127.0.0.1:${POSTGRES_PORT:-5432}/${TEST_DB}"
echo "restore_pg_drill: migrate check on $TEST_DB …" >&2
python infrastructure/postgresql/migrate.py check

COUNT="$("${DC[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc 'SELECT COUNT(*) FROM cars')"
echo "restore_pg_drill: OK cars=$COUNT in $TEST_DB (prod DB untouched)" >&2
