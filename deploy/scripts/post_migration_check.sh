#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/rideauto}"
API_URL="${API_URL:-http://127.0.0.1:8080}"
MEILI_URL="${MEILI_URL:-http://127.0.0.1:7700}"
POSTGRES_USER="${POSTGRES_USER:-wra}"
POSTGRES_DB="${POSTGRES_DB:-wra}"
MEILI_INDEX="${MEILI_INDEX:-cars}"
MEILI_MASTER_KEY="${MEILI_MASTER_KEY:-}"

cd "$PROJECT_DIR"

if docker compose version &>/dev/null; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose &>/dev/null; then
  DOCKER_COMPOSE=(docker-compose)
else
  echo "ERROR: need 'docker compose' (v2) or docker-compose (v1) in PATH" >&2
  exit 1
fi

echo "==> 1) Containers status"
"${DOCKER_COMPOSE[@]}" ps

echo "==> 2) API smoke"
for path in "/api/health" "/api/search?per_page=2"; do
  code="$(curl -sS -o /tmp/wra_smoke_body.txt -w "%{http_code}" "${API_URL}${path}" || echo "000")"
  if [[ "$code" != "200" ]]; then
    echo "API smoke failed: GET ${path} -> HTTP ${code}" >&2
    head -c 2000 /tmp/wra_smoke_body.txt >&2 || true
    echo >&2
    echo "Подсказка: 500 на /api/search часто invalid_api_key — сравните длину ключа (должно совпадать):" >&2
    echo "  docker compose exec -T api sh -c 'printf %s \"\$WRA_MEILISEARCH_KEY\" | wc -c'" >&2
    echo "  docker compose exec -T meilisearch sh -c 'printf %s \"\$MEILI_MASTER_KEY\" | wc -c'" >&2
    exit 1
  fi
done
rm -f /tmp/wra_smoke_body.txt
echo "API health/search: OK"

echo "==> 3) PostgreSQL cars count"
PG_COUNT="$(
  "${DOCKER_COMPOSE[@]}" exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT COUNT(*) FROM cars;"
)"
echo "cars in PostgreSQL: $PG_COUNT"

echo "==> 4) Pick one random car id from PostgreSQL"
SAMPLE_CAR_ID="$(
  "${DOCKER_COMPOSE[@]}" exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT car_id FROM cars ORDER BY random() LIMIT 1;"
)"
if [[ -z "${SAMPLE_CAR_ID}" ]]; then
  echo "ERROR: cannot sample car_id from PostgreSQL"
  exit 1
fi
echo "sample car_id: $SAMPLE_CAR_ID"

echo "==> 5) Validate /api/car/{id}"
python3 - <<PY
import json
import urllib.request
import urllib.parse
import sys

api = "${API_URL}"
cid = "${SAMPLE_CAR_ID}"
url = f"{api}/api/car/{urllib.parse.quote(cid)}"
try:
    with urllib.request.urlopen(url, timeout=20) as r:
        body = json.loads(r.read().decode("utf-8"))
except Exception as e:
    print(f"ERROR: /api/car check failed: {e}")
    sys.exit(1)

obj = body.get("result") or {}
if not isinstance(obj, dict) or not obj:
    print("ERROR: /api/car returned empty result")
    sys.exit(1)
print("api/car sample check: OK")
PY

echo "==> 6) Meili index stats"
MEILI_HEADERS=()
if [[ -n "$MEILI_MASTER_KEY" ]]; then
  MEILI_HEADERS=(-H "Authorization: Bearer ${MEILI_MASTER_KEY}")
fi
MEILI_STATS="$(curl -fsS "${MEILI_HEADERS[@]}" "$MEILI_URL/indexes/$MEILI_INDEX/stats")"
# Нельзя пайпить JSON в `python3 - <<'PY'` — stdin уходит на heredoc, json.load(stdin) получает пусто.
if [[ -z "$MEILI_STATS" ]]; then
  echo "ERROR: Meilisearch stats response empty (URL $MEILI_URL/indexes/$MEILI_INDEX/stats)" >&2
  exit 1
fi
echo "$MEILI_STATS" | python3 -c "import json,sys; s=json.load(sys.stdin); print('meili numberOfDocuments:', s.get('numberOfDocuments'))"

echo "==> 7) Summary"
echo "Post-migration smoke checks passed."
