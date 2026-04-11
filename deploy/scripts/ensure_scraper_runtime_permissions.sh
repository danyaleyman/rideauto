#!/usr/bin/env bash
# Однократно на проде: владелец logs/ и локальных *.db под пользователя systemd-сервиса корейского цикла.
#
# prod-encar-auto-update.service → User=prod-encar (ночной Encar-каталог)
#
# Если `sudo -u prod-encar pip install …` в .venv даёт Permission denied — владелец .venv после «pip от root»
# не совпадает с пользователем сервиса. Исправление:
#   sudo WRA_RUNTIME_USER=prod-encar WRA_RUNTIME_GROUP=prod-encar WRA_CHOWN_VENV=1 bash deploy/scripts/ensure_scraper_runtime_permissions.sh
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

install -d -m 0775 -o "$OWNER" -g "$GROUP" "$ROOT/logs"
# Файлы в logs/ (например logs/scraper.log из scraper_config.yaml) могли быть созданы от root.
chown -R "$OWNER:$GROUP" "$ROOT/logs"
chmod -R u+rwX,g+rwX "$ROOT/logs" 2>/dev/null || true

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

if [[ "${WRA_CHOWN_VENV:-0}" == "1" ]] && [[ -d "$ROOT/.venv" ]]; then
  # Частичная установка от root → каталоги в site-packages недоступны prod-encar для pip upgrade.
  shopt -s nullglob
  for sp in "$ROOT"/.venv/lib/python3.*/site-packages; do
    [[ -d "$sp" ]] || continue
    rm -rf "$sp/hangul_romanize" "$sp/hangul_romanize-"*.dist-info 2>/dev/null || true
  done
  shopt -u nullglob
  chown -R "$OWNER:$GROUP" "$ROOT/.venv"
  chmod -R u+rwX "$ROOT/.venv"
  echo "OK: $ROOT/.venv → $OWNER:$GROUP + u+rwX (удалён частичный hangul_romanize при наличии)"
fi

echo "OK: $ROOT — logs/ и локальные *.db (если есть) для $OWNER:$GROUP"
