#!/usr/bin/env bash
# Обёртка для совместимости — используйте deploy/scripts/backup_pg.sh (ротация + rclone).
exec "$(cd "$(dirname "$0")" && pwd)/backup_pg.sh" "$@"
