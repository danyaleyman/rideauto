#!/usr/bin/env bash
# Однократно на проде: владелец logs/ и локальных *.db под пользователя systemd-сервиса корейского цикла.
#
# encar-update.service          → User=www-data (по умолчанию ниже)
# prod-encar-auto-update.service → User=prod-encar
#
# Примеры:
#   sudo bash deploy/scripts/ensure_scraper_runtime_permissions.sh
#   sudo WRA_RUNTIME_USER=prod-encar WRA_RUNTIME_GROUP=prod-encar bash deploy/scripts/ensure_scraper_runtime_permissions.sh
set -euo pipefail
ROOT="${WRA_REPO_ROOT:-/opt/prod-encar}"
OWNER="${WRA_RUNTIME_USER:-www-data}"
GROUP="${WRA_RUNTIME_GROUP:-www-data}"

if [[ ! -d "$ROOT" ]]; then
  echo "Directory not found: $ROOT" >&2
  exit 1
fi

install -d -m 0755 -o "$OWNER" -g "$GROUP" "$ROOT/logs"

for f in encar_cars.db encar_china.db scraper_checkpoint.db scraper.log auto_update.log; do
  # *.db — только если остались после миграции; чекпоинт сейчас в Postgres.
  if [[ -e "$ROOT/$f" ]]; then
    chown "$OWNER:$GROUP" "$ROOT/$f" || true
    chmod u+rw,g+rw "$ROOT/$f" 2>/dev/null || chmod 664 "$ROOT/$f" || true
  fi
done

# WAL / SHM рядом с основной БД
shopt -s nullglob
for f in "$ROOT"/encar_cars.db-* "$ROOT"/encar_china.db-* "$ROOT"/scraper_checkpoint.db-*; do
  [[ -e "$f" ]] || continue
  chown "$OWNER:$GROUP" "$f" || true
done
for f in "$ROOT"/*.scraper.checkpoint.json "$ROOT"/*.scraper.checkpoint.json.tmp; do
  [[ -e "$f" ]] || continue
  chown "$OWNER:$GROUP" "$f" || true
  chmod u+rw,g+rw "$f" 2>/dev/null || chmod 664 "$f" || true
done
shopt -u nullglob

echo "OK: $ROOT — logs/ и локальные *.db (если есть) для $OWNER:$GROUP"
