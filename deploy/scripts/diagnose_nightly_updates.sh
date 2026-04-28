#!/usr/bin/env bash
# Что смотреть, если ночью не отработали rideauto-auto-update / dongchedi-update.
# Запуск на сервере: bash deploy/scripts/diagnose_nightly_updates.sh
# Или из /opt/rideauto: bash deploy/scripts/diagnose_nightly_updates.sh

set +e

echo "=== Таймеры (должны быть active) ==="
for u in dongchedi-update.timer rideauto-auto-update.timer prod-dongchedi-update.timer rideauto-meilisearch-sync.timer; do
  if systemctl list-unit-files "$u" &>/dev/null; then
    systemctl is-enabled "$u" 2>/dev/null && systemctl status "$u" --no-pager -l || true
    echo "---"
  fi
done

echo
echo "=== Последние запуски rideauto-auto-update (Encar каталог) ==="
journalctl -u rideauto-auto-update.service -n 120 --no-pager 2>/dev/null || true

echo
echo "=== Последние запуски dongchedi-update (Китай) ==="
journalctl -u dongchedi-update.service -u prod-dongchedi-update.service -n 120 --no-pager 2>/dev/null || journalctl -u dongchedi-update.service -n 120 --no-pager

echo
echo "=== Сводка: когда сработает (systemd) ==="
systemctl list-timers --all --no-pager 2>/dev/null | grep -E "encar|dongchedi|meilisearch|rideauto" || true

echo
echo "=== Последний запуск Meilisearch sync ==="
journalctl -u rideauto-meilisearch-sync.service -n 80 --no-pager 2>/dev/null || true

echo
echo "=== Подсказка ==="
echo "1) rideauto-auto-update.service: ошибки Postgres, прокси (ENCAR_PROXY_URLS), encar_scraper; см. journal выше."
echo "2) Ручной прогон: sudo -u rideauto /opt/rideauto/deploy/scripts/run_encar_daily_once_prod.sh"
echo "3) encar_daily_update / encar_scraper — см. logs/scraper.log при настройке в scraper_config.yaml."
