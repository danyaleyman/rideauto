#!/usr/bin/env bash
# Ежедневный бэкап PostgreSQL (docker compose) + ротация + опциональная выгрузка в облако.
#
# Установка (на VPS, из корня репозитория /opt/rideauto):
#   sudo cp deploy/systemd/rideauto-pg-backup.{service,timer} /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now rideauto-pg-backup.timer
#
# Облако (опционально): установите rclone, настройте remote «yandex»:
#   rclone config   # type: webdav / yandex disk / mail.ru cloud
#   export RCLONE_REMOTE=yandex:rideauto-backups
#
# Переменные:
#   BACKUP_DIR          — каталог дампов (по умолчанию ./backups)
#   BACKUP_RETENTION_DAYS — сколько дней хранить локально (14)
#   RCLONE_REMOTE       — например yandex:rideauto-backups (пусто = без upload)
#   COMPOSE_PROJECT     — если не rideauto в /opt/rideauto

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION="${BACKUP_RETENTION_DAYS:-14}"
mkdir -p "$OUT_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$OUT_DIR/wra_${STAMP}.dump"
LATEST_LINK="$OUT_DIR/wra_latest.dump"

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
else
  echo "backup_pg: docker compose not found" >&2
  exit 1
fi

POSTGRES_USER="${POSTGRES_USER:-wra}"
POSTGRES_DB="${POSTGRES_DB:-wra}"

echo "backup_pg: dumping to $FILE …" >&2
"${DC[@]}" exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc >"$FILE"
chmod 600 "$FILE"
ln -sf "$(basename "$FILE")" "$LATEST_LINK"

SIZE="$(du -h "$FILE" | cut -f1)"
echo "backup_pg: ok size=$SIZE file=$FILE" >&2

# Локальная ротация
find "$OUT_DIR" -maxdepth 1 -name 'wra_*.dump' -type f -mtime +"$RETENTION" -delete 2>/dev/null || true

REMOTE="${RCLONE_REMOTE:-}"
if [[ -n "$REMOTE" ]] && command -v rclone >/dev/null 2>&1; then
  echo "backup_pg: uploading to $REMOTE …" >&2
  rclone copyto "$FILE" "${REMOTE}/wra_${STAMP}.dump" --retries 3 --low-level-retries 10
  rclone copyto "$FILE" "${REMOTE}/wra_latest.dump" --retries 3
  echo "backup_pg: cloud upload done" >&2
fi

# Маркер для мониторинга (health_watchdog / внешний cron)
echo "$STAMP $(date -Is) $SIZE" >>"$OUT_DIR/backup.log"
