#!/usr/bin/env bash
# Из корня репозитория: docker compose up -d postgres && bash backend/scripts/run_encar_smoke_docker.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
docker compose up -d postgres
export DATABASE_URL="${DATABASE_URL:-postgresql://wra:wra@postgres:5432/wra}"
echo "=== encar_scraper --max-cars 10 ==="
docker compose run --rm \
  -v "$ROOT:/repo:ro" -w /repo/backend \
  -e PYTHONPATH=/repo/backend \
  -e DATABASE_URL="$DATABASE_URL" \
  -e SKIP_POSTGRES_CATALOG_SYNC=1 \
  -e SKIP_FRONTEND_EXPORT=1 \
  api python encar_scraper.py --config /repo/scraper_config.smoke.yaml --max-cars 10
echo "=== encar_daily_update --once ==="
docker compose run --rm \
  -v "$ROOT:/repo:ro" -w /repo/backend \
  -e PYTHONPATH=/repo/backend \
  -e DATABASE_URL="$DATABASE_URL" \
  -e SKIP_POSTGRES_CATALOG_SYNC=1 \
  -e SKIP_FRONTEND_EXPORT=1 \
  api python encar_daily_update.py --config /repo/scraper_config.smoke.yaml --once
echo "Готово."
