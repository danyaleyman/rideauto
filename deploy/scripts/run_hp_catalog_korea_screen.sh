#!/usr/bin/env bash
# Encar (Korea): sync уникальных trim → hp_catalog.db → DeepSeek → power_hp в cars.
# Запуск в screen:
#   bash /opt/rideauto/deploy/scripts/run_hp_catalog_korea_screen.sh
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG="${LOG_DIR}/hp_catalog_korea_${STAMP}.log"

if [[ -f /etc/default/rideauto ]]; then
  set -a
  # shellcheck source=/dev/null
  source /etc/default/rideauto
  set +a
fi
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT}/.env"
  set +a
fi

PG_DSN="${SYNC_PG_DSN:-${DATABASE_URL:-${WRA_PG_DSN:-}}}"
if [[ -z "${DATABASE_URL// /}" ]] && [[ -n "${PG_DSN// /}" ]]; then
  export DATABASE_URL="$PG_DSN"
fi
if [[ -z "${DATABASE_URL// /}" ]]; then
  echo "run_hp_catalog_korea_screen: задайте DATABASE_URL в /etc/default/rideauto" >&2
  exit 1
fi

if [[ -z "${DEEPSEEK_API_KEY:-}" ]] && [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "run_hp_catalog_korea_screen: задайте DEEPSEEK_API_KEY или OPENAI_API_KEY в /etc/default/rideauto" >&2
  exit 1
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate"
REWRITE_PY="${ROOT}/deploy/scripts/pg_dsn_host_local_rewrite.py"
if [[ -f "$REWRITE_PY" ]]; then
  export DATABASE_URL="$(printf '%s' "${DATABASE_URL}" | python "${REWRITE_PY}")"
fi
export PYTHONPATH="${ROOT}/backend"
export PYTHONUNBUFFERED=1

DB_PATH="${HP_CATALOG_DB_PATH:-${ROOT}/data/hp_catalog.db}"

{
  echo "=== hp catalog korea start $(date -Is) ==="
  echo "log=$LOG db=$DB_PATH"

  while true; do
    echo "--- cycle $(date -Is) ---"

    echo "[sync] encar keys from postgres → hp_catalog.db"
    python -u "${ROOT}/backend/scripts/sync_hp_catalog_from_postgres.py" \
      --dsn "$DATABASE_URL" \
      --db "$DB_PATH" \
      --source encar \
      --only-missing-hp

    echo "[llm] fill pending hp via DeepSeek/OpenAI"
    python -u "${ROOT}/backend/scripts/fill_hp_catalog_deepseek.py" \
      --db "$DB_PATH" \
      --provider auto \
      --model deepseek-chat \
      --openai-model gpt-4o-mini \
      --retry-errors \
      --max-attempts 8

    echo "[apply] backfill cars.power_hp from hp_catalog"
    python -u "${ROOT}/backend/scripts/backfill_cars_power_from_hp_catalog.py" \
      --dsn "$DATABASE_URL" \
      --source encar

    python -u "${ROOT}/backend/scripts/hp_catalog_stats.py" --db "$DB_PATH"

    IDLE="${HP_KOREA_CYCLE_SLEEP_SEC:-120}"
    echo "[idle] sleep ${IDLE}s before next cycle"
    sleep "$IDLE"
  done
} 2>&1 | tee -a "$LOG"
