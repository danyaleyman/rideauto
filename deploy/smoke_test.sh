#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8080}"
DB_PATH="${DB_PATH:-/opt/prod-encar/encar_cars.db}"
ENV_FILE="${ENV_FILE:-/etc/default/prod-encar}"

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
need_cmd sqlite3

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

json_get() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json,sys
f,expr=sys.argv[1],sys.argv[2]
obj=json.load(open(f,'r',encoding='utf-8'))
parts=[p for p in expr.split('.') if p]
cur=obj
for p in parts:
    if isinstance(cur, list):
        cur=cur[int(p)]
    else:
        cur=cur.get(p)
print("" if cur is None else cur)
PY
}

request() {
  local method="$1"
  local url="$2"
  local outfile="$3"
  local auth="${4:-}"
  local data="${5:-}"
  local code
  if [[ -n "$auth" && -n "$data" ]]; then
    code="$(curl -sS -o "$outfile" -w "%{http_code}" -X "$method" "$url" -H "Authorization: Bearer $auth" -H "Content-Type: application/json" -d "$data")"
  elif [[ -n "$auth" ]]; then
    code="$(curl -sS -o "$outfile" -w "%{http_code}" -X "$method" "$url" -H "Authorization: Bearer $auth")"
  elif [[ -n "$data" ]]; then
    code="$(curl -sS -o "$outfile" -w "%{http_code}" -X "$method" "$url" -H "Content-Type: application/json" -d "$data")"
  else
    code="$(curl -sS -o "$outfile" -w "%{http_code}" -X "$method" "$url")"
  fi
  echo "$code"
}

info "1) Проверка health"
HEALTH_JSON="$TMP_DIR/health.json"
CODE="$(request GET "$API_BASE/api/health" "$HEALTH_JSON")"
[[ "$CODE" == "200" ]] || fail "Health endpoint вернул HTTP $CODE"
STATUS="$(json_get "$HEALTH_JSON" "status")"
[[ "$STATUS" == "ok" ]] || fail "Health status != ok"
pass "API health"

info "2) Создание тестового пользователя и токена в SQLite"
TOKEN="$(python3 - "$DB_PATH" <<'PY'
import sqlite3, secrets, datetime, json, sys
db=sys.argv[1]
conn=sqlite3.connect(db)
conn.row_factory=sqlite3.Row
now=datetime.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"
exp=(datetime.datetime.utcnow()+datetime.timedelta(days=30)).replace(microsecond=0).isoformat()+"Z"
conn.execute("""INSERT INTO users (tg_id,username,first_name,last_name,photo_url,raw_json,created_at,updated_at)
VALUES (?,?,?,?,?,?,?,?)
ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name,last_name=excluded.last_name,photo_url=excluded.photo_url,raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
("999999001","smoke_user","Smoke","Test","",json.dumps({"id":"999999001"}),now,now))
u=conn.execute("SELECT id FROM users WHERE tg_id=?",("999999001",)).fetchone()
token=secrets.token_urlsafe(32)
conn.execute("INSERT INTO user_sessions (token,user_id,created_at,expires_at,last_seen_at) VALUES (?,?,?,?,?)",(token,u["id"],now,exp,now))
conn.commit()
print(token)
PY
)"
[[ -n "$TOKEN" ]] || fail "Не удалось создать тестовый токен"
pass "Тестовый токен создан"

info "3) Проверка /api/me"
ME_JSON="$TMP_DIR/me.json"
CODE="$(request GET "$API_BASE/api/me" "$ME_JSON" "$TOKEN")"
[[ "$CODE" == "200" ]] || fail "/api/me вернул HTTP $CODE"
ME_ID="$(json_get "$ME_JSON" "user.id")"
[[ -n "$ME_ID" ]] || fail "В /api/me пустой user.id"
pass "/api/me"

info "4) Выбор car_id для тестов"
CAR_ID="$(sqlite3 "$DB_PATH" "select car_id from cars limit 1;")"
[[ -n "$CAR_ID" ]] || fail "Не найден car_id в таблице cars"
pass "car_id=$CAR_ID"

info "5) Избранное: add/list"
ADD_FAV_JSON="$TMP_DIR/add_fav.json"
CODE="$(request POST "$API_BASE/api/favorites" "$ADD_FAV_JSON" "$TOKEN" "{\"car_id\":\"$CAR_ID\",\"note\":\"smoke note\"}")"
[[ "$CODE" == "200" ]] || fail "POST /api/favorites вернул HTTP $CODE"
LIST_FAV_JSON="$TMP_DIR/list_fav.json"
CODE="$(request GET "$API_BASE/api/favorites" "$LIST_FAV_JSON" "$TOKEN")"
[[ "$CODE" == "200" ]] || fail "GET /api/favorites вернул HTTP $CODE"
python3 - "$LIST_FAV_JSON" "$CAR_ID" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],'r',encoding='utf-8'))
cid=sys.argv[2]
rows=obj.get("result") or []
ok=any(str(r.get("car_id"))==cid for r in rows)
raise SystemExit(0 if ok else 1)
PY
pass "Избранное работает"

info "6) История: add/list"
ADD_HIST_JSON="$TMP_DIR/add_hist.json"
CODE="$(request POST "$API_BASE/api/history" "$ADD_HIST_JSON" "$TOKEN" "{\"car_id\":\"$CAR_ID\"}")"
[[ "$CODE" == "200" ]] || fail "POST /api/history вернул HTTP $CODE"
LIST_HIST_JSON="$TMP_DIR/list_hist.json"
CODE="$(request GET "$API_BASE/api/history?limit=5" "$LIST_HIST_JSON" "$TOKEN")"
[[ "$CODE" == "200" ]] || fail "GET /api/history вернул HTTP $CODE"
pass "История работает"

info "7) Подписки: add/list"
ADD_SUB_JSON="$TMP_DIR/add_sub.json"
CODE="$(request POST "$API_BASE/api/subscriptions" "$ADD_SUB_JSON" "$TOKEN" '{"name":"Smoke BMW","filters":{"marks":"BMW","price_to":"5000"}}')"
[[ "$CODE" == "200" ]] || fail "POST /api/subscriptions вернул HTTP $CODE"
LIST_SUB_JSON="$TMP_DIR/list_sub.json"
CODE="$(request GET "$API_BASE/api/subscriptions" "$LIST_SUB_JSON" "$TOKEN")"
[[ "$CODE" == "200" ]] || fail "GET /api/subscriptions вернул HTTP $CODE"
pass "Подписки работают"

info "8) Compare"
CMP_JSON="$TMP_DIR/compare.json"
CODE="$(request GET "$API_BASE/api/compare?ids=$CAR_ID" "$CMP_JSON")"
[[ "$CODE" == "200" ]] || fail "GET /api/compare вернул HTTP $CODE"
pass "Сравнение работает"

info "9) Checkout create/list"
ADD_CHK_JSON="$TMP_DIR/add_checkout.json"
CODE="$(request POST "$API_BASE/api/checkout" "$ADD_CHK_JSON" "$TOKEN" "{\"car_ids\":[\"$CAR_ID\"],\"contact\":\"@smoke_user\",\"comment\":\"smoke checkout\"}")"
[[ "$CODE" == "200" ]] || fail "POST /api/checkout вернул HTTP $CODE"
LIST_CHK_JSON="$TMP_DIR/list_checkout.json"
CODE="$(request GET "$API_BASE/api/checkout" "$LIST_CHK_JSON" "$TOKEN")"
[[ "$CODE" == "200" ]] || fail "GET /api/checkout вернул HTTP $CODE"
pass "Checkout работает"

if [[ -f "$ENV_FILE" ]]; then
  info "10) Проверка раннера уведомлений"
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  if [[ -n "${SUBSCRIPTIONS_ADMIN_KEY:-}" ]]; then
    NOTIFY_JSON="$TMP_DIR/notify.json"
    CODE="$(curl -sS -o "$NOTIFY_JSON" -w "%{http_code}" -X POST "$API_BASE/api/subscriptions/run-notifications" -H "X-Admin-Key: $SUBSCRIPTIONS_ADMIN_KEY")"
    [[ "$CODE" == "200" ]] || fail "run-notifications вернул HTTP $CODE"
    pass "Раннер уведомлений работает"
  else
    info "SUBSCRIPTIONS_ADMIN_KEY в $ENV_FILE не задан, шаг уведомлений пропущен"
  fi
else
  info "Файл env ($ENV_FILE) не найден, шаг уведомлений пропущен"
fi

pass "Smoke-test завершен успешно"
