#!/usr/bin/env bash
# Разовый цикл Кореи: encar_daily_update --once (+ при postgres — экспорт в cars.json / chunks / фасеты).
# Запуск от root: скрипт выполнит шAGи от www-data (или ENCAR_RUN_USER).
# Сразу после успеха статика frontend/ обновлена (если есть encar_cars.db); при proxy_cache для /api при необходимости: nginx reload.
set -euo pipefail

ROOT="${ROOT:-/opt/prod-encar}"
PY="${PY:-$ROOT/.venv/bin/python}"
CFG="${ENCAR_SCRAPER_CONFIG:-$ROOT/scraper_config.yaml}"
SQLITE_DB="${ENCAR_SQLITE_CATALOG:-$ROOT/encar_cars.db}"
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

echo "=== 1/2 encar_daily_update.py --once (cwd=$ROOT) ==="
run_py "$PY" "$ROOT/backend/encar_daily_update.py" --once --config "$CFG"

BACKEND="$("$PY" -c "import yaml,sys; c=yaml.safe_load(open(sys.argv[1],encoding='utf-8')); print((c.get('storage') or {}).get('backend','sqlite'))" "$CFG")"

# При storage.backend=sqlite экспорт уже внутри encar_daily_update / encar_scraper.
# При postgres (и т.п.) каталог на сайте = encar_cars.db — догоняем экспорт явно.
if [[ -f "$SQLITE_DB" ]] && { [[ "$BACKEND" != "sqlite" ]] || [[ "${FORCE_EXPORT:-}" == "1" ]]; }; then
  echo "=== 2/2 export_from_scraper_db.py → frontend (storage.backend=$BACKEND) ==="
  LEARN=(--learn-engine-map)
  if [[ "${SKIP_LEARN_ENGINE_MAP:-}" =~ ^(1|true|yes)$ ]]; then
    LEARN=()
  fi
  run_py "$PY" "$ROOT/backend/export_from_scraper_db.py" \
    --db "$SQLITE_DB" \
    --out "$ROOT/frontend/cars.json" \
    --chunk-size 5000 \
    --chunk-dir "$ROOT/frontend/data/chunks" \
    --chunk-index "$ROOT/frontend/data/cars.index.json" \
    --gzip \
    "${LEARN[@]}"
else
  if [[ ! -f "$SQLITE_DB" ]]; then
    echo "Файл $SQLITE_DB не найден — шаг экспорта пропущен (если каталог только в Postgres, нужен отдельный пайплайн)." >&2
  else
    echo "=== 2/2 экспорт уже выполнен внутри цикла (storage.backend=sqlite) ==="
  fi
fi

echo "Готово."
echo "Если /api отдаётся из nginx proxy_cache — сбросьте зону или: sudo nginx -s reload"
