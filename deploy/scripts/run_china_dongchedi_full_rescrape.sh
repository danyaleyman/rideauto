#!/usr/bin/env bash
# Полный перескрейп Китая: все марки (--shard-brands), enrich → PostgreSQL (dongchedi_scraper.yaml).
# Нужен DATABASE_URL / storage.postgres.dsn при backend=postgres.
# После прогона при необходимости: infrastructure/meilisearch/sync_meilisearch.py (или ночной общий sync).
# Перед запуском остановите таймер, чтобы не писали в одну БД два процесса:
#   sudo systemctl stop dongchedi-update.timer prod-dongchedi-update.timer 2>/dev/null || true
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
PY="${PY:-$ROOT/.venv/bin/python}"
DB="${ENCAR_CHINA_DB:-$ROOT/encar_china.db}"
YAML_CAND=(
  "$ROOT/backend/dongchedi_scraper.yaml"
  "$ROOT/dongchedi_scraper.yaml"
)
YAML=""
for f in "${YAML_CAND[@]}"; do
  if [[ -f "$f" ]]; then YAML="$f"; break; fi
done
if [[ -z "$YAML" ]]; then
  echo "Не найден dongchedi_scraper.yaml (искал: ${YAML_CAND[*]})" >&2
  exit 1
fi

CP="$(dirname "$DB")/$(basename "$DB" .db).scraper.checkpoint.json"
if [[ -f "$CP" ]]; then
  echo "Удаляю checkpoint (начнём с первого shard): $CP"
  rm -f "$CP"
else
  echo "Checkpoint не найден — ок: $CP"
fi

export PYTHONUNBUFFERED=1
cd "$ROOT/backend"

echo "Запуск dongchedi.scraper: --shard-brands --db $DB --config $YAML"
if [[ "$(id -un)" == "root" ]]; then
  exec sudo -u "${ENCAR_RUN_USER:-www-data}" "$PY" -m dongchedi.scraper \
    --config "$YAML" \
    --db "$DB" \
    --shard-brands
else
  exec "$PY" -m dongchedi.scraper \
    --config "$YAML" \
    --db "$DB" \
    --shard-brands
fi
