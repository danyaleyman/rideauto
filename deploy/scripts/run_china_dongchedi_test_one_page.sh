#!/usr/bin/env bash
# Тестовая выгрузка Dongchedi: 1 страница листинга + enrich (карточка + фото + params-carIds).
# Не пишет checkpoint (--no-checkpoint). Лимит сохранений — CHINA_TEST_LIMIT (по умолчанию 24).
#
# После прогона: перезапустите API, откройте каталог ?region=china и карточку dongchedi-<sku>.
# Проверка БД: см. вывод «Проверка последних записей» в конце (PostgreSQL).
set -euo pipefail

ROOT="${ROOT:-/opt/prod-encar}"
PY="${PY:-$ROOT/.venv/bin/python}"
PG_DSN="${DATABASE_URL:-}"
YAML_CAND=(
  "$ROOT/backend/dongchedi_scraper.yaml"
  "$ROOT/dongchedi_scraper.yaml"
)
YAML=""
for f in "${YAML_CAND[@]}"; do
  if [[ -f "$f" ]]; then YAML="$f"; break; fi
done
LIMIT="${CHINA_TEST_LIMIT:-24}"
RUN_USER="${ENCAR_RUN_USER:-www-data}"

if [[ -z "$YAML" ]]; then
  echo "Не найден dongchedi_scraper.yaml" >&2
  exit 1
fi

cd "$ROOT/backend"
export PYTHONUNBUFFERED=1

echo "=== Dongchedi тест: max-pages=1, limit=$LIMIT, enrich=ON, без checkpoint ==="
echo "    DATABASE_URL=${PG_DSN:+set}"
echo "    config=$YAML"

run_scrape() {
  if [[ "$(id -un)" == "root" ]]; then
    sudo -u "$RUN_USER" "$PY" -m dongchedi.scraper \
      --config "$YAML" \
      --max-pages 1 \
      --limit "$LIMIT" \
      --no-checkpoint
  else
    "$PY" -m dongchedi.scraper \
      --config "$YAML" \
      --max-pages 1 \
      --limit "$LIMIT" \
      --no-checkpoint
  fi
}

run_scrape

echo ""
echo "=== Проверка последних записей Dongchedi в PostgreSQL (фото / specs / пробег) ==="
"$PY" <<'PY'
import json
import os
import psycopg2

dsn = (os.environ.get("DATABASE_URL") or "").strip()
if not dsn:
    print("DATABASE_URL не задан — пропуск SQL-проверки.")
    raise SystemExit(0)

conn = psycopg2.connect(dsn)
cur = conn.cursor()
cur.execute(
    """
    SELECT car_id, data
    FROM cars
    WHERE source = 'dongchedi'
    ORDER BY id DESC
    LIMIT 8
    """
)
rows = cur.fetchall()
if not rows:
    print("Нет строк source=dongchedi — проверьте лимит/сеть/антибот.")
else:
    for car_id, raw in rows:
        payload = raw if isinstance(raw, dict) else {}
        d = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        imgs = d.get("images")
        if isinstance(imgs, str):
            try:
                imgs = json.loads(imgs)
            except Exception:
                imgs = []
        nimg = len(imgs) if isinstance(imgs, list) else 0
        print(
            car_id,
            "photos=" + str(nimg),
            "specs=" + ("yes" if d.get("dongchedi_specs_url") else "no"),
            "km=" + str(d.get("km_age", "")),
            "my_price=" + str(d.get("my_price", "")),
        )
cur.close()
conn.close()
PY

echo ""
echo "Дальше: sudo systemctl restart <ваш-api-сервис>"
echo "Каталог: https://ВАШ-ДОМЕН/catalog?region=china"
echo "Полный цикл без лимита: sudo bash deploy/scripts/run_china_dongchedi_full_rescrape.sh"
