#!/usr/bin/env bash
# Che168 (China) — полный обход каталога на хосте (полный репозиторий + .venv + PostgreSQL).
#
# Замеры 2026-10-24 (globalapi.che168.com/api/v1/search):
#   * pageindex работает на любую глубину (page=1000 отдаёт данные), страницы стабильны
#     и не пересекаются; pagesize максимум 100 (200 → пустая выдача).
#   * price/year фильтры API игнорирует, поэтому сегментация price×year не нужна:
#     полный каталог = обычный обход брендов до pagecount, 639 брендов ≈ 2 379 страниц.
# Сегментация осталась опцией (CHE168_FULL_SEGMENTATION=1) на случай, если фильтры заработают.
#
# Примеры:
#   bash deploy/scripts/run_che168_scraper_full_host.sh 0        # без лимита (полный каталог)
#   bash deploy/scripts/run_che168_scraper_full_host.sh 5000     # ограничить новые сохранения
#   CHE168_FULL_RESET_OFFSETS=1 bash deploy/scripts/run_che168_scraper_full_host.sh 0
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
  echo "ERROR: DATABASE_URL или SYNC_PG_DSN / WRA_PG_DSN" >&2
  exit 1
fi

PY="${PYTHON:-${ROOT}/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: нет интерпретатора ($PY); создайте .venv или задайте PYTHON=/path/to/python" >&2
  exit 1
fi

REWRITE_PY="${ROOT}/deploy/scripts/pg_dsn_host_local_rewrite.py"
PG_DSN="$(printf '%s' "${PG_DSN}" | "${PY}" "${REWRITE_PY}")"

export DATABASE_URL="$PG_DSN"
export RIDEAUTO_PG_CHECKPOINT_DSN="$PG_DSN"

CFG="${CHE168_SCRAPER_CONFIG:-${ROOT}/che168_scraper.yaml}"
if [[ ! -f "$CFG" ]]; then
  echo "ERROR: нет конфига $CFG" >&2
  exit 1
fi

MAX="${1:-0}"
EXTRA_ARGS=(--max-cars "$MAX")

# Сегментация price×year по умолчанию ВЫКЛючена: Che168 игнорирует фильтры цены/года,
# поэтому сегменты лишь повторяют один и тот же обход (10×8 = 80 дублей).
# Включить (CHE168_FULL_SEGMENTATION=1) только если API начнёт фильтровать.
if [[ "${CHE168_FULL_SEGMENTATION:-0}" = "1" ]]; then
  EXTRA_ARGS+=(--segmentation)
fi
# Полный обход с нуля: сбросить brand_*/segment_* чекпоинты и начать с первой страницы.
if [[ "${CHE168_FULL_RESET_OFFSETS:-0}" = "1" ]]; then
  EXTRA_ARGS+=(--reset-offsets)
fi

# Каталог принадлежит единственному пайплайну rideauto-catalog-pipeline.timer
# (ADR 0004, deploy/docs/SCALE.md) — свой postgres/Meili sync не запускаем.
export SKIP_POSTGRES_CATALOG_SYNC=1
export SKIP_FRONTEND_EXPORT=1
export PYTHONPATH="${ROOT}/backend"
export PYTHONUNBUFFERED=1

echo "ROOT=$ROOT"
echo "CONFIG=$CFG DATABASE_URL=<скрыто> PYTHONPATH=$PYTHONPATH"
echo "max_cars=$MAX args=${EXTRA_ARGS[*]}"
exec "$PY" "${ROOT}/backend/che168_scraper.py" --config "$CFG" "${EXTRA_ARGS[@]}"
