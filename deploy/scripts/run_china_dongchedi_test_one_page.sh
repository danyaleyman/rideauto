#!/usr/bin/env bash
# Тестовая выгрузка Dongchedi: 1 страница листинга + enrich (карточка + фото + params-carIds).
# Не пишет checkpoint (--no-checkpoint). Лимит сохранений — CHINA_TEST_LIMIT (по умолчанию 24).
#
# После прогона: перезапустите API, откройте каталог ?region=china и карточку dongchedi-<sku>.
# Проверка БД: см. вывод «Проверка последних записей» в конце.
set -euo pipefail

ROOT="${ROOT:-/opt/prod-encar}"
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
LIMIT="${CHINA_TEST_LIMIT:-24}"
RUN_USER="${ENCAR_RUN_USER:-www-data}"

if [[ -z "$YAML" ]]; then
  echo "Не найден dongchedi_scraper.yaml" >&2
  exit 1
fi

cd "$ROOT/backend"
export PYTHONUNBUFFERED=1

echo "=== Dongchedi тест: max-pages=1, limit=$LIMIT, enrich=ON, без checkpoint ==="
echo "    DB=$DB"
echo "    config=$YAML"

run_scrape() {
  if [[ "$(id -un)" == "root" ]]; then
    sudo -u "$RUN_USER" "$PY" -m dongchedi.scraper \
      --config "$YAML" \
      --db "$DB" \
      --max-pages 1 \
      --limit "$LIMIT" \
      --no-checkpoint
  else
    "$PY" -m dongchedi.scraper \
      --config "$YAML" \
      --db "$DB" \
      --max-pages 1 \
      --limit "$LIMIT" \
      --no-checkpoint
  fi
}

run_scrape

echo ""
echo "=== Проверка последних записей Dongchedi в БД (фото / specs / пробег) ==="
"$PY" - "$DB" <<'PY'
import json, sqlite3, sys

db = sys.argv[1]
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """
    SELECT car_id, data_json FROM cars
    WHERE json_extract(data_json, '$.data.source') = 'dongchedi'
    ORDER BY id DESC
    LIMIT 8
    """
).fetchall()
if not rows:
    print("Нет строк source=dongchedi — проверьте лимит/сеть/антибот.")
else:
    for r in rows:
        raw = json.loads(r["data_json"])
        d = raw.get("data") or {}
        cid = r["car_id"]
        imgs = []
        try:
            imgs = json.loads(d.get("images") or "[]")
        except Exception:
            pass
        nimg = len(imgs) if isinstance(imgs, list) else 0
        print(
            cid,
            "photos=" + str(nimg),
            "specs=" + ("yes" if d.get("dongchedi_specs_url") else "no"),
            "km=" + str(d.get("km_age", "")),
            "my_price=" + str(d.get("my_price", "")),
        )
conn.close()
PY

echo ""
echo "Дальше: sudo systemctl restart <ваш-api-сервис>   # чтобы API открыл свежий encar_china.db"
echo "Каталог: https://ВАШ-ДОМЕН/catalog?region=china"
echo "Полный цикл без лимита: sudo bash deploy/scripts/run_china_dongchedi_full_rescrape.sh"
