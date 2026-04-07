#!/usr/bin/env bash
set -euo pipefail
# Снимок БД wra в каталог backups/ (custom format pg_dump -Fc).
# Запуск из корня репозитория: ./deploy/scripts/backup_postgres_compose.sh
# Требует docker compose и сервис postgres.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$OUT_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$OUT_DIR/wra_${STAMP}.dump"

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
else
  echo "docker compose not found" >&2
  exit 1
fi

POSTGRES_USER="${POSTGRES_USER:-wra}"
POSTGRES_DB="${POSTGRES_DB:-wra}"

"${DC[@]}" exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$FILE"
echo "backup written: $FILE ($(du -h "$FILE" | cut -f1))"
