#!/usr/bin/env bash
# Синхронизация PostgreSQL → Meilisearch с хоста (полный репозиторий в /opt/rideauto).
# Переменные: см. /etc/default/rideauto — нужен DSN Postgres, доступный с этого хоста.
# Важно: не используйте хостнейм образа compose «postgres» в DSN при запуске с хоста — только 127.0.0.1/локальный проброс порта.
#
# Полная перезаливка индекса (удаляет UID index и создаёт заново по текущей БД):
#   bash deploy/scripts/run_meilisearch_sync_host.sh --recreate-index
# Путь к PATCH settings (по умолчанию infrastructure/meilisearch/index_settings.json в $ROOT):
#   WRA_MEILISEARCH_SETTINGS=/opt/rideauto/infrastructure/meilisearch/index_settings.json
# Опционально отключить префлайт, если включён через .env:
#   unset WRA_MEILI_PREFLIGHT_GATE
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

REWRITE_PY="${ROOT}/deploy/scripts/pg_dsn_host_local_rewrite.py"
if [[ -f "$REWRITE_PY" ]]; then
  PG_DSN="$(printf '%s' "${PG_DSN}" | /usr/bin/python3 "${REWRITE_PY}")"
fi

MEILI_URL="${WRA_MEILISEARCH_URL:-http://127.0.0.1:7700}"
# Ключ должен совпадать с MEILI_MASTER_KEY у контейнера meilisearch (см. .env / docker compose).
# Если в шелле старый ключ — unset MEILI_MASTER_KEY WRA_MEILISEARCH_KEY и подставьте актуальный или оставьте пустым для dev без ключа.
MEILI_KEY="${MEILI_MASTER_KEY:-${WRA_MEILISEARCH_KEY:-}}"
INDEX="${WRA_MEILISEARCH_INDEX:-cars}"
LIVE_INDEX="${WRA_MEILI_LIVE_INDEX:-cars}"
# Безопасная публикация: полная перезаливка в staging UID, затем swap с боевым (API продолжает читать LIVE_INDEX).
# Задайте WRA_MEILISEARCH_INDEX=cars_build (staging), WRA_MEILI_LIVE_INDEX=cars, WRA_MEILI_SWAP_INTO_LIVE=1.
SETTINGS="${WRA_MEILISEARCH_SETTINGS:-$ROOT/infrastructure/meilisearch/index_settings.json}"
SYNC_PY="$ROOT/infrastructure/meilisearch/sync_meilisearch.py"

if [[ ! -f "$SYNC_PY" ]]; then
  echo "Не найден $SYNC_PY (нужен полный клон репозитория в $ROOT)" >&2
  exit 1
fi

if [[ ! -f "$SETTINGS" ]]; then
  echo "run_meilisearch_sync_host: нет файла настроек Meili: $SETTINGS" >&2
  echo "  Задайте WRA_MEILISEARCH_SETTINGS или положите index_settings.json в infrastructure/meilisearch/." >&2
  echo "  Не подставляйте буквально «...» вместо пути (это не имя файла)." >&2
  exit 1
fi

SWAP_ARGS=()
case "${WRA_MEILI_SWAP_INTO_LIVE:-}" in
  1|true|TRUE|yes|YES|on|ON)
    SWAP_ARGS+=(--swap-into-live "--live-index-name" "$LIVE_INDEX")
    ;;
esac

exec /usr/bin/python3 "$SYNC_PY" \
  --pg-dsn "$PG_DSN" \
  --meili-url "$MEILI_URL" \
  ${MEILI_KEY:+--meili-key "$MEILI_KEY"} \
  --index-name "$INDEX" \
  --settings "$SETTINGS" \
  --batch-size "${MEILISEARCH_SYNC_BATCH:-500}" \
  "${SWAP_ARGS[@]}" \
  "$@"
