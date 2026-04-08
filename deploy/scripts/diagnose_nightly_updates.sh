#!/usr/bin/env bash
# Что смотреть, если ночью не отработали encar-update / dongchedi-update.
# Запуск на сервере: bash deploy/scripts/diagnose_nightly_updates.sh
# Или из /opt/prod-encar: bash deploy/scripts/diagnose_nightly_updates.sh

set +e

echo "=== Таймеры (должны быть active) ==="
for u in encar-update.timer dongchedi-update.timer prod-encar-auto-update.timer prod-dongchedi-update.timer; do
  if systemctl list-unit-files "$u" &>/dev/null; then
    systemctl is-enabled "$u" 2>/dev/null && systemctl status "$u" --no-pager -l || true
    echo "---"
  fi
done

echo
echo "=== Последние запуски encar-update (Корея / auto_update) ==="
journalctl -u encar-update.service -u prod-encar-auto-update.service -n 120 --no-pager 2>/dev/null || journalctl -u encar-update.service -n 120 --no-pager

echo
echo "=== Последние запуски dongchedi-update (Китай) ==="
journalctl -u dongchedi-update.service -u prod-dongchedi-update.service -n 120 --no-pager 2>/dev/null || journalctl -u dongchedi-update.service -n 120 --no-pager

echo
echo "=== Подсказка ==="
echo "1) encar-update.service: смотрите ошибки PostgreSQL, EncarSystem.daily_update, либо «encar_daily_update завершился с кодом» в конце."
echo "2) Если catalog_encar_nightly в backend/config.json true и Postgres доступен, после цикла EncarSystem идёт encar_daily_update.py --once — его падение роняет весь юнит."
echo "3) auto_update пишет в logs/auto_update.log от корня репо (если www-data может писать)."
echo "4) encar_daily_update / encar_scraper — см. logs/scraper.log при настройке в scraper_config.yaml."
