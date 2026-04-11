#!/usr/bin/env bash
# Разовый цикл Кореи (часто User=www-data). На rideauto VPS проще: deploy/scripts/run_encar_daily_once_prod.sh (User=prod-encar).
# encar_daily_update --once → encar_scraper (--only-pending) → postgres_catalog_sync внутри скрейпера.
set -euo pipefail

ROOT="${ROOT:-/opt/prod-encar}"
PY="${PY:-$ROOT/.venv/bin/python}"
CFG="${ENCAR_SCRAPER_CONFIG:-$ROOT/scraper_config.yaml}"
RUN_USER="${ENCAR_RUN_USER:-www-data}"

cd "$ROOT"
if [[ ! -f "$CFG" ]]; then
  echo "Нет конфига: $CFG" >&2
  exit 1
fi

run_py() {
  if [[ "$(id -un)" == "root" ]]; then
    sudo -u "$RUN_USER" env PYTHONUNBUFFERED=1 "$@"
  else
    env PYTHONUNBUFFERED=1 "$@"
  fi
}

echo "=== encar_daily_update.py --once (cwd=$ROOT) ==="
run_py "$PY" "$ROOT/backend/encar_daily_update.py" --once --config "$CFG"

echo "Готово. При proxy_cache для /api — сброс зоны или: sudo nginx -s reload"
