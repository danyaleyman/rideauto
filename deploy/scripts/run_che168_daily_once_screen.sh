#!/usr/bin/env bash
# Разовый Che168 daily (discover + sold + --only-pending) в screen.
#   bash /opt/rideauto/deploy/scripts/run_che168_daily_once_screen.sh
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG="${LOG_DIR}/che168_daily_${STAMP}.log"

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

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate"
REWRITE_PY="${ROOT}/deploy/scripts/pg_dsn_host_local_rewrite.py"
if [[ -f "$REWRITE_PY" ]]; then
  export DATABASE_URL="$(printf '%s' "${DATABASE_URL}" | python "${REWRITE_PY}")"
fi
export PYTHONUNBUFFERED=1

{
  echo "=== che168 daily start $(date -Is) ==="
  echo "log=$LOG"
  python -u "${ROOT}/backend/che168_daily_update.py" \
    --once \
    --config "${ROOT}/che168_scraper.yaml"
  echo "=== che168 daily done $(date -Is) exit=$? ==="
} 2>&1 | tee -a "$LOG"

echo "Finished. Log: $LOG"
