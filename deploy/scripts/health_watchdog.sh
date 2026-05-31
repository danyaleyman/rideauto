#!/usr/bin/env bash
# Проверка /api/health?deep=1 — для cron/systemd (exit 1 → алерт внешнего мониторинга).
#
#   HEALTH_URL=https://rideauto.ru/api/health?deep=1 ./deploy/scripts/health_watchdog.sh
#
set -euo pipefail

URL="${HEALTH_URL:-http://127.0.0.1:8080/api/health?deep=1}"
TIMEOUT="${HEALTH_TIMEOUT_SEC:-15}"

body="$(curl -fsS --max-time "$TIMEOUT" "$URL")"
echo "$body"
export BODY="$body"

python3 - <<'PY'
import json, os, sys
d = json.loads(os.environ["BODY"])
status = d.get("status")
if status not in ("ok", "degraded"):
    print("UNHEALTHY:", d, file=sys.stderr)
    sys.exit(1)
checks = d.get("checks") or {}
for name in ("postgres", "meilisearch"):
    c = checks.get(name) or {}
    if not c.get("ok"):
        print(f"check failed: {name}", c, file=sys.stderr)
        sys.exit(1)
if checks.get("meilisearch", {}).get("stale"):
    print("meilisearch stale:", checks["meilisearch"], file=sys.stderr)
    sys.exit(1)
print("health_watchdog: ok status=", status)
PY
