#!/usr/bin/env bash
# Encar scraper с хоста (полный репозиторий + корневой scraper_config.yaml + .venv).
# Пример: sudo -u ubuntu bash deploy/scripts/run_encar_scraper_max_cars_host.sh 1000
#
# Нужно: PYTHONPATH backend, DATABASE_URL до Postgres С ХОСТА (localhost:5432, не postgres:5432).
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
cd "$ROOT"

if [[ -f /etc/default/rideauto ]]; then
  set -a
  # shellcheck source=/dev/null
  source /etc/default/rideauto
  set +a
fi

PG_DSN="${DATABASE_URL:-${SYNC_PG_DSN:-${WRA_PG_DSN:-}}}"
if [[ -z "${PG_DSN// /}" ]]; then
  echo "ERROR: DATABASE_URL или SYNC_PG_DSN / WRA_PG_DSN для подключения с хоста (127.0.0.1:5432)" >&2
  exit 1
fi
export DATABASE_URL="$PG_DSN"

CFG="${WRA_SCRAPER_CONFIG:-${ROOT}/scraper_config.yaml}"
MAX="${1:-1000}"

PY="${PYTHON:-${ROOT}/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: нет интерпретатора ($PY); создайте .venv или задайте PYTHON=/path/to/python" >&2
  exit 1
fi

if [[ ! -f "$CFG" ]]; then
  echo "ERROR: нет конфига $CFG" >&2
  exit 1
fi

export PYTHONPATH="${ROOT}/backend"
export PYTHONUNBUFFERED=1

echo "ROOT=$ROOT"
echo "CONFIG=$CFG DATABASE_URL=<скрыто> PYTHONPATH=$PYTHONPATH"
echo "max_cars=$MAX"
exec "$PY" "${ROOT}/backend/encar_scraper.py" --config "$CFG" "--max-cars" "$MAX"
