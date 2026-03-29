#!/usr/bin/env bash
# Первичная полная выгрузка каталога Encar на сервере (импорт + местные, см. scraper_config.yaml car_types / max_cars).
# После завершения: encar_cars.db, экспорт в frontend/*.json, расчёт цен (внутри export_from_scraper_db → price.py).
set -euo pipefail
REPO_ROOT="${1:-/opt/prod-encar}"
cd "$REPO_ROOT"
PY="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "Укажите интерпретатор: PYTHON=/path/to/python $0" >&2
  exit 1
fi
export PYTHONUNBUFFERED=1
CONFIG="${ENCAR_SCRAPER_CONFIG:-$REPO_ROOT/scraper_config.yaml}"
echo "Репозиторий: $REPO_ROOT"
echo "Конфиг: $CONFIG"
echo "Запуск encar_scraper.py (полный list + детали; в конце — экспорт на фронт с ценами)..."
"$PY" "$REPO_ROOT/backend/encar_scraper.py" --config "$CONFIG"
echo "Первичная выгрузка завершена."
