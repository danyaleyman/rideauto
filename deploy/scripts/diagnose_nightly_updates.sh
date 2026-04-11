#!/usr/bin/env bash
# Что смотреть, если ночью не отработали prod-encar-auto-update / dongchedi-update.
# Запуск на сервере: bash deploy/scripts/diagnose_nightly_updates.sh
# Или из /opt/prod-encar: bash deploy/scripts/diagnose_nightly_updates.sh

set +e

echo "=== Таймеры (должны быть active) ==="
for u in dongchedi-update.timer prod-encar-auto-update.timer prod-dongchedi-update.timer prod-encar-meilisearch-sync.timer; do
  if systemctl list-unit-files "$u" &>/dev/null; then
    systemctl is-enabled "$u" 2>/dev/null && systemctl status "$u" --no-pager -l || true
    echo "---"
  fi
done

echo
echo "=== Последние запуски prod-encar-auto-update (Encar каталог) ==="
journalctl -u prod-encar-auto-update.service -n 120 --no-pager 2>/dev/null || true

echo
echo "=== Последние запуски dongchedi-update (Китай) ==="
journalctl -u dongchedi-update.service -u prod-dongchedi-update.service -n 120 --no-pager 2>/dev/null || journalctl -u dongchedi-update.service -n 120 --no-pager

echo
echo "=== Сводка: когда сработает (systemd) ==="
systemctl list-timers --all --no-pager 2>/dev/null | grep -E "encar|dongchedi|meilisearch|prod-encar" || true

echo
echo "=== Последний запуск Meilisearch sync ==="
journalctl -u prod-encar-meilisearch-sync.service -n 80 --no-pager 2>/dev/null || true

echo
echo "=== Подсказка ==="
echo "1) prod-encar-auto-update.service: ошибки Postgres, прокси (ENCAR_PROXY_URLS), encar_scraper; см. journal выше."
echo "2) Ручной прогон: sudo -u prod-encar /opt/prod-encar/deploy/scripts/run_encar_daily_once_prod.sh"
echo "3) encar_daily_update / encar_scraper — см. logs/scraper.log при настройке в scraper_config.yaml."
