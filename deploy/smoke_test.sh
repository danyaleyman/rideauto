#!/usr/bin/env bash
# Быстрая проверка публичного FastAPI (каталог в Postgres + Meilisearch).
#   API_BASE=http://127.0.0.1:8080 bash deploy/smoke_test.sh
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8080}"

RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
NC=$'\033[0m'

pass() { echo "${GREEN}[PASS]${NC} $1"; }
fail() { echo "${RED}[FAIL]${NC} $1"; exit 1; }
info() { echo "${YELLOW}[INFO]${NC} $1"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Не найдена команда: $1"
}

need_cmd curl
need_cmd python3

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

json_get() {
  python3 - "$1" "$2" <<'PY'
import json, sys
f, expr = sys.argv[1], sys.argv[2]
obj = json.load(open(f, encoding="utf-8"))
parts = [p for p in expr.split(".") if p]
cur = obj
for p in parts:
    if isinstance(cur, list):
        cur = cur[int(p)]
    else:
        cur = cur.get(p)
print("" if cur is None else cur)
PY
}

request() {
  local url="$1"
  local outfile="$2"
  curl -sS -o "$outfile" -w "%{http_code}" "$url"
}

info "1) GET /api/health"
H="$TMP_DIR/health.json"
CODE="$(request "$API_BASE/api/health" "$H")"
[[ "$CODE" == "200" ]] || fail "health HTTP $CODE"
[[ "$(json_get "$H" status)" == "ok" ]] || fail "health status != ok"
pass "health"

info "2) GET /api/cars"
C="$TMP_DIR/cars.json"
CODE="$(request "$API_BASE/api/cars?per_page=1" "$C")"
[[ "$CODE" == "200" ]] || fail "/api/cars HTTP $CODE"
CAR_ID="$(python3 -c "import json,sys; o=json.load(open(sys.argv[1],encoding='utf-8')); r=o.get('result')or[]; print((r[0].get('id') or r[0].get('car_id') or '') if r else '')" "$C")" || true
if [[ -z "${CAR_ID:-}" ]]; then
  info "каталог пуст — пропуск карточки и фасетов с данными"
else
  pass "cars (sample id=$CAR_ID)"
  info "3) GET /api/car/{id}"
  P="$TMP_DIR/car.json"
  CODE="$(request "$API_BASE/api/car/$CAR_ID" "$P")"
  [[ "$CODE" == "200" ]] || fail "/api/car HTTP $CODE"
  pass "car detail"
fi

info "4) GET /api/facets"
F="$TMP_DIR/facets.json"
CODE="$(request "$API_BASE/api/facets" "$F")"
[[ "$CODE" == "200" ]] || fail "/api/facets HTTP $CODE"
pass "facets"

info "5) GET /api/filters"
FL="$TMP_DIR/filters.json"
CODE="$(request "$API_BASE/api/filters" "$FL")"
[[ "$CODE" == "200" ]] || fail "/api/filters HTTP $CODE"
pass "filters"

pass "Smoke-test завершен успешно"
