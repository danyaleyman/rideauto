#!/usr/bin/env bash
# Первичная полная выгрузка Encar (storage.backend=postgres + DATABASE_URL / dsn в scraper_config.yaml).
# После прогона: строки в Postgres, опционально postgres_catalog_sync / Meilisearch (см. encar_scraper.py).
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
echo "Запуск encar_scraper.py (полный list + детали; запись в Postgres)..."
"$PY" "$REPO_ROOT/backend/encar_scraper.py" --config "$CONFIG"
echo "Первичная выгрузка завершена."
