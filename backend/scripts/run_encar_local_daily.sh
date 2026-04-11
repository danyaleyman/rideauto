#!/usr/bin/env bash
# Один цикл encar_daily_update в локальную Postgres (docker-compose postgres на 127.0.0.1:5432).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://wra:wra@127.0.0.1:5432/wra}"
export SKIP_POSTGRES_CATALOG_SYNC="${SKIP_POSTGRES_CATALOG_SYNC:-1}"
export SKIP_FRONTEND_EXPORT="${SKIP_FRONTEND_EXPORT:-1}"
CFG="$ROOT/scraper_config.yaml"
if [[ ! -f "$ROOT/scraper_config.local.yaml" ]]; then
  echo "Подсказка: скопируйте scraper_config.local.example.yaml -> scraper_config.local.yaml" >&2
fi
cd "$ROOT/backend"
PYTHONPATH=. python encar_daily_update.py --config "$CFG" --once
