# RideAuto autorepair

Автономный агент: **probe → diagnose → remediate → verify** для стека docker compose.

## Команды

Из корня репозитория (на сервере `/opt/rideauto`):

```bash
python -m deploy.autorepair probe       # снимок всех проб (JSON, exit 1 при сбое)
python -m deploy.autorepair run-once    # один цикл с починкой
python -m deploy.autorepair daemon      # непрерывный цикл (systemd)
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `WRA_AUTOREPAIR_ENABLED` | `0` | Включить remediation (не только probe) |
| `WRA_AUTOREPAIR_DRY_RUN` | `1` | Логировать план без `docker compose` |
| `WRA_AUTOREPAIR_INTERVAL_SEC` | `30` | Интервал daemon (мин. 5) |
| `WRA_AUTOREPAIR_COOLDOWN_SEC` | `300` | Пауза между одинаковыми действиями |
| `WRA_AUTOREPAIR_MAX_ACTIONS_PER_HOUR` | `20` | Лимит действий в час |
| `WRA_AUTOREPAIR_ALLOW_RESTART` | `1` | `docker compose restart` |
| `WRA_AUTOREPAIR_ALLOW_MEILI_SYNC` | `1` | sync Meilisearch из PG |
| `WRA_AUTOREPAIR_ALLOW_MIGRATE` | `0` | `migrate apply` (осторожно) |
| `WRA_AUTOREPAIR_WEBHOOK_URL` | — | Slack/Telegram webhook при эскалации |
| `WRA_AUTOREPAIR_API_HEALTH` | `http://127.0.0.1:8080/api/health?deep=1` | Deep health API |

Состояние и журнал: `var/autorepair/state.json`, `var/autorepair/events.log` (в `.gitignore`).

## Цепочка

`postgres` → `redis` / `meilisearch` → `api` → `web` → `edge`

Корневая причина — первый упавший компонент, у которого зависимости ниже по стеку здоровы. При `meili_stale` в deep health — приоритет `meili_sync`, иначе restart сервиса compose.

## Продакшен

1. Сначала: `WRA_AUTOREPAIR_DRY_RUN=1`, `run-once`, проверить лог.
2. Затем: `WRA_AUTOREPAIR_DRY_RUN=0`, `WRA_AUTOREPAIR_ENABLED=1`.
3. Systemd: `deploy/systemd/rideauto-autorepair.service` → `/etc/systemd/system/`, `systemctl enable --now rideauto-autorepair`.

Интервал **1 с** не рекомендуется: нагрузка на API/docker и риск restart-loop. Минимум 5 с, по умолчанию 30 с.

## Связанные скрипты

- `deploy/scripts/health_watchdog.sh` — лёгкий HTTP watchdog
- `deploy/ops` — ручные операции (meili sync, migrate, deploy)
