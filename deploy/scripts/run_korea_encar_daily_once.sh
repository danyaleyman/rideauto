#!/usr/bin/env bash
# Разовый ночной цикл Кореи без таймера: новые листинги + проданные + encar_scraper --only-pending + экспорт.
set -euo pipefail

ROOT="${ROOT:-/opt/prod-encar}"
PY="${PY:-$ROOT/.venv/bin/python}"
CFG="${ENCAR_SCRAPER_CONFIG:-$ROOT/scraper_config.yaml}"

cd "$ROOT"
if [[ ! -f "$CFG" ]]; then
  echo "Нет конфига: $CFG" >&2
  exit 1
fi

echo "Запуск: encar_daily_update.py --once (cwd=$ROOT)"
if [[ "$(id -un)" == "root" ]]; then
  exec sudo -u "${ENCAR_RUN_USER:-www-data}" env PYTHONUNBUFFERED=1 "$PY" "$ROOT/backend/encar_daily_update.py" --once --config "$CFG"
else
  exec env PYTHONUNBUFFERED=1 "$PY" "$ROOT/backend/encar_daily_update.py" --once --config "$CFG"
fi
