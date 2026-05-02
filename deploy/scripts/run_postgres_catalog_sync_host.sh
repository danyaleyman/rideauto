#!/usr/bin/env bash
# Ручной postgres_catalog_sync на хосте: DSN из /etc/default/rideauto (как Meilisearch-скрипт).
# Не передавайте пароль в argv — только через EnvironmentFile.
# Полный каталог (сотни тыс. строк) + цены + Meili — часто десятки минут и дольше; не прерывайте без причины.
#
#   sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_postgres_catalog_sync_host.sh
#   sudo -u rideauto bash .../run_postgres_catalog_sync_host.sh --no-meilisearch
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
if [[ -f /etc/default/rideauto ]]; then
  set -a
  # shellcheck source=/dev/null
  source /etc/default/rideauto
  set +a
fi

PG_DSN="${SYNC_PG_DSN:-${DATABASE_URL:-${WRA_PG_DSN:-}}}"
if [[ -z "${DATABASE_URL// /}" ]] && [[ -n "${PG_DSN// /}" ]]; then
  export DATABASE_URL="$PG_DSN"
fi

if [[ -z "${DATABASE_URL// /}" ]]; then
  echo "run_postgres_catalog_sync_host: задайте DATABASE_URL, WRA_PG_DSN или SYNC_PG_DSN в /etc/default/rideauto" >&2
  exit 1
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate"
REWRITE_PY="${ROOT}/deploy/scripts/pg_dsn_host_local_rewrite.py"
if [[ -f "$REWRITE_PY" ]]; then
  export DATABASE_URL="$(printf '%s' "${DATABASE_URL}" | python "${REWRITE_PY}")"
fi
export PYTHONPATH="${ROOT}/backend"
export PYTHONUNBUFFERED=1
CFG="${WRA_SCRAPER_CONFIG:-${ROOT}/scraper_config.yaml}"

echo "run_postgres_catalog_sync_host: старт (долго при большом каталоге; лог — в этот терминал и stderr)…" >&2
exec python -u "${ROOT}/backend/postgres_catalog_sync.py" --config "$CFG" "$@"
