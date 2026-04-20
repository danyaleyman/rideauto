#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/opt/prod-encar}"
cd "$ROOT"

DB_PATH="${HP_CATALOG_DB_PATH:-$ROOT/data/hp_catalog.db}"
PG_DSN="${DATABASE_URL:-${WRA_PG_DSN:-}}"
if [[ -z "$PG_DSN" ]]; then
  echo "ERROR: set DATABASE_URL or WRA_PG_DSN"
  exit 2
fi

echo "[1/3] Sync hp_catalog from postgres..."
/opt/prod-encar/.venv/bin/python backend/scripts/sync_hp_catalog_from_postgres.py \
  --dsn "$PG_DSN" \
  --db "$DB_PATH" \
  --source encar

echo "[2/3] Fill pending rows via LLM..."
/opt/prod-encar/.venv/bin/python backend/scripts/fill_hp_catalog_deepseek.py \
  --db "$DB_PATH" \
  --provider auto \
  --model deepseek-chat \
  --openai-model gpt-4o-mini \
  --retry-errors \
  --max-attempts 8

echo "[3/4] Apply hp_catalog power to cars table..."
/opt/prod-encar/.venv/bin/python backend/scripts/backfill_cars_power_from_hp_catalog.py \
  --dsn "$PG_DSN" \
  --source encar

echo "[4/4] Stats:"
/opt/prod-encar/.venv/bin/python backend/scripts/hp_catalog_stats.py --db "$DB_PATH"

