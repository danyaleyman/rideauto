#!/usr/bin/env bash
# Backfill Che168 price_cny + полный postgres_catalog_sync (цены ₽, Meili).
# Запуск в screen:
#   bash /opt/rideauto/deploy/scripts/run_che168_price_backfill_screen.sh
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG="${LOG_DIR}/che168_price_backfill_${STAMP}.log"

if [[ -f /etc/default/rideauto ]]; then
  set -a
  # shellcheck source=/dev/null
  source /etc/default/rideauto
  set +a
fi

PG_DSN="${SYNC_PG_DSN:-${DATABASE_URL:-${WRA_PG_DSN:-}}}"
if [[ -z "${DATABASE_URL// /}" ]] && [[ -n "${PG_DSN// /}" ]]; then
  export DATABASE_URL="$PG_DSN"
fi
if [[ -z "${DATABASE_URL// /}" ]]; then
  echo "run_che168_price_backfill_screen: задайте DATABASE_URL в /etc/default/rideauto" >&2
  exit 1
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate"
REWRITE_PY="${ROOT}/deploy/scripts/pg_dsn_host_local_rewrite.py"
if [[ -f "$REWRITE_PY" ]]; then
  export DATABASE_URL="$(printf '%s' "${DATABASE_URL}" | python "${REWRITE_PY}")"
fi
export RIDEAUTO_PG_CHECKPOINT_DSN="$DATABASE_URL"
export PYTHONPATH="${ROOT}/backend"
export PYTHONUNBUFFERED=1

{
  echo "=== che168 price backfill start $(date -Is) ==="
  echo "log=$LOG"

  echo "--- phase 1: backfill price_cny in cars.data ---"
  python -u "${ROOT}/backend/scripts/backfill_che168_price_cny.py" \
    --config "${ROOT}/che168_scraper.yaml" \
    --only-legacy-raw \
    --batch-size 500 \
    --apply

  echo "--- phase 2: postgres_catalog_sync (prices + meili) ---"
  CFG="${WRA_SCRAPER_CONFIG:-${ROOT}/scraper_config.yaml}"
  python -u "${ROOT}/backend/postgres_catalog_sync.py" \
    --config "$CFG" \
    --process-batch-size 400 \
    --batch-commit 400

  echo "=== done $(date -Is) ==="
} 2>&1 | tee -a "$LOG"

echo "Finished. Log: $LOG"
