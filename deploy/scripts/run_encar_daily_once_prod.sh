#!/usr/bin/env bash
# Одноразовый encar_daily_update на проде (без подстановки DSN вручную).
# Запуск от пользователя сервиса, например:
#   sudo -u prod-encar bash /opt/prod-encar/deploy/scripts/run_encar_daily_once_prod.sh
#
# Нужны: /etc/default/prod-encar (или иной файл) с реальным DATABASE_URL / WRA_PG_DSN;
#         venv в /opt/prod-encar/.venv; права на logs/ — см. ensure_scraper_runtime_permissions.sh
#
# Опционально: WRA_SCRAPER_CONFIG=/opt/prod-encar/deploy/scraper_config.probe-20.yaml — тест на 20 новых INSERT.
set -euo pipefail
ROOT="${WRA_REPO_ROOT:-/opt/prod-encar}"
ENV_FILE="${WRA_ENV_FILE:-/etc/default/prod-encar}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# Часто в unit задают WRA_PG_DSN; скрейпер читает DATABASE_URL
if [[ -z "${DATABASE_URL:-}" ]] && [[ -n "${WRA_PG_DSN:-}" ]]; then
  export DATABASE_URL="$WRA_PG_DSN"
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "run_encar_daily_once_prod: задайте DATABASE_URL или WRA_PG_DSN в $ENV_FILE" >&2
  exit 1
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate"
export PYTHONPATH="${ROOT}/backend"
CFG="${WRA_SCRAPER_CONFIG:-${ROOT}/scraper_config.yaml}"
exec python "${ROOT}/backend/encar_daily_update.py" --config "${CFG}" --once
