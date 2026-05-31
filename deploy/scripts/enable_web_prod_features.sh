#!/usr/bin/env bash
# Включает фичи web из технического roadmap в /opt/rideauto/.env и пересобирает контейнер web.
# Запуск на VPS: sudo bash /opt/rideauto/deploy/scripts/enable_web_prod_features.sh
set -eu
if set -o pipefail 2>/dev/null; then :; fi

ROOT="${WRA_REPO_ROOT:-/opt/rideauto}"
ENV_FILE="${WRA_ENV_FILE:-$ROOT/.env}"
cd "$ROOT"

upsert() {
  local key="$1"
  local val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    printf '\n%s=%s\n' "$key" "$val" >>"$ENV_FILE"
  fi
}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

# Виртуализация каталога (build-time)
upsert "NEXT_PUBLIC_FEATURE_VIRTUAL_LIST" "1"

# CSP enforce: включите после недели report-only без нарушений в консоли браузера.
if grep -q "^CSP_ENFORCE=1" "$ENV_FILE" 2>/dev/null || grep -q "^NEXT_PUBLIC_CSP_ENFORCE=1" "$ENV_FILE" 2>/dev/null; then
  upsert "CSP_ENFORCE" "1"
  upsert "NEXT_PUBLIC_CSP_ENFORCE" "1"
fi

# Sentry: не перезаписываем, если уже задан в .env
if ! grep -q "^NEXT_PUBLIC_SENTRY_DSN=" "$ENV_FILE" 2>/dev/null; then
  echo "WARN: NEXT_PUBLIC_SENTRY_DSN не задан — добавьте DSN в $ENV_FILE и перезапустите скрипт." >&2
fi

# ISR warm: топ-12 id из API (korea), если curl доступен
if [[ -z "${WRA_ISR_WARM_CAR_REFS:-}" ]]; then
  WARM=""
  if command -v curl >/dev/null 2>&1; then
    WARM="$(
      curl -fsS "http://127.0.0.1:8080/api/cars?region=korea&per_page=12&page=1" 2>/dev/null \
        | python3 -c "
import json,sys
try:
  d=json.load(sys.stdin)
  ids=[str(x.get('id','')).strip() for x in d.get('result',[]) if x.get('id')]
  print(','.join(ids[:12]))
except Exception:
  pass
" 2>/dev/null || true
    )"
  fi
  if [[ -n "$WARM" ]]; then
    upsert "WRA_ISR_WARM_CAR_REFS" "$WARM"
    echo "ISR warm refs: $WARM"
  else
    echo "WARN: не удалось получить id для WRA_ISR_WARM_CAR_REFS — задайте вручную в .env" >&2
  fi
else
  upsert "WRA_ISR_WARM_CAR_REFS" "$WRA_ISR_WARM_CAR_REFS"
fi

echo "=== .env (web feature keys) ==="
grep -E '^(NEXT_PUBLIC_FEATURE|NEXT_PUBLIC_SENTRY|WRA_ISR_WARM)' "$ENV_FILE" || true

echo "=== docker compose build web ==="
docker compose build web
docker compose up -d --no-deps web
docker compose ps web

echo "=== docker compose build api (facet/catalog) ==="
docker compose build api
docker compose up -d --no-deps api
docker compose ps api

echo "Done. Проверка: curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/catalog"
