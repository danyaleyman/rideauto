#!/usr/bin/env bash
# Host-side Korea HP/Nm backfill. DSN from /etc/default/rideauto, never printed.
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
if [[ -f /etc/default/rideauto ]]; then
  set -a
  # shellcheck source=/dev/null
  source /etc/default/rideauto
  set +a
fi

PG_DSN="${SYNC_PG_DSN:-${DATABASE_URL:-${WRA_PG_DSN:-}}}"
if [[ -z "${DATABASE_URL:-}" ]] && [[ -n "${PG_DSN}" ]]; then
  export DATABASE_URL="$PG_DSN"
fi
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "run_korea_hp_backfill_host: need DATABASE_URL / WRA_PG_DSN / SYNC_PG_DSN" >&2
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

echo "run_korea_hp_backfill_host: starting…" >&2
exec python -u "${ROOT}/backend/scripts/backfill_korea_power_torque.py" "$@"
