#!/usr/bin/env bash
# Синхронизация PostgreSQL → Meilisearch с хоста (полный репозиторий в /opt/rideauto).
# Переменные: см. /etc/default/rideauto — нужен DSN Postgres, доступный с этого хоста.
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
if [[ -f /etc/default/rideauto ]]; then
  # shellcheck source=/dev/null
  . /etc/default/rideauto
fi

PG_DSN="${SYNC_PG_DSN:-${DATABASE_URL:-${WRA_PG_DSN:-}}}"

if [[ -z "${PG_DSN// /}" ]]; then
  echo "run_meilisearch_sync_host: задайте SYNC_PG_DSN или DATABASE_URL в /etc/default/rideauto (DSN с хоста, напр. postgresql://wra:...@127.0.0.1:5432/wra)" >&2
  exit 1
fi

MEILI_URL="${WRA_MEILISEARCH_URL:-http://127.0.0.1:7700}"
MEILI_KEY="${MEILI_MASTER_KEY:-${WRA_MEILISEARCH_KEY:-}}"
INDEX="${WRA_MEILISEARCH_INDEX:-cars}"
SETTINGS="$ROOT/infrastructure/meilisearch/index_settings.json"
SYNC_PY="$ROOT/infrastructure/meilisearch/sync_meilisearch.py"

if [[ ! -f "$SYNC_PY" ]]; then
  echo "Не найден $SYNC_PY (нужен полный клон репозитория в $ROOT)" >&2
  exit 1
fi

exec /usr/bin/python3 "$SYNC_PY" \
  --pg-dsn "$PG_DSN" \
  --meili-url "$MEILI_URL" \
  ${MEILI_KEY:+--meili-key "$MEILI_KEY"} \
  --index-name "$INDEX" \
  --settings "$SETTINGS" \
  --batch-size "${MEILISEARCH_SYNC_BATCH:-500}"
