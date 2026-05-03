# Release runbook (упрощённо): канареечные флаги, откат

## Feature flags

| Где | Что |
|-----|-----|
| **Frontend (build-time)** | `NEXT_PUBLIC_FEATURE_*` в `.env` → `docker compose build web` → `up -d web`. |
| **Backend (runtime)** | Переменные `WRA_*` в окружении `api` / systemd; перезапуск процесса без обязательной пересборки образа. |

Полноценный **флаг-сервис** (LaunchDarkly, Unleash, флаги в Redis) в репозитории не подключён; при росте команды — вынести чтение флагов в API и отдавать клиенту `GET /api/flags`.

## Канареечная выкладка (идея)

1. Собрать образ `web` с тегом `:candidate` и выкатить на **один** инстанс / путь `/preview` за nginx `split_clients` или отдельный поддомен.
2. Сравнить ошибки (Sentry), latency (`/metrics`), конверсию форм.
3. Промотировать тег в `:prod` на всех инстансах.

Практика «два compose-проекта на одном хосте» возможна (`COMPOSE_PROJECT_NAME`); детали зависят от вашего nginx.

## Откат frontend (Docker)

```bash
cd /opt/rideauto
git checkout <previous-tag>
docker compose build web
docker compose up -d web
```

## Откат Meilisearch после swap

Повторный **swap** между теми же UID возвращает предыдущее содержимое индексов (см. `RUNBOOK_OPERATIONS.md`).

## On-call

Минимум: доступ к логам `docker compose logs -f api web`, `GET /api/health`, Grafana/Prometheus при наличии. Расширенный runbook: `deploy/docs/RUNBOOK_OPERATIONS.md`.

### Шаблон эскалации (процесс команды, не автоматика)

1. **S1** — инцидент заведён, дежурный смотрит логи/метрики в течение 15 минут.
2. **S2** — нет улучшения или затронуты платежи/юридически значимые потоки — второй человек + уведомление канала.
3. **S3** — полная недоступность или утечка данных — остановка деплоя, сохранение артефактов (логи, конфиги), постмортем в течение 5 рабочих дней.

Контакты и мессенджеры — вне репозитория; при желании добавьте `docs/ON_CALL.md` только для внутренней ссылки на PagerDuty/Slack (без секретов).

### Runtime feature flags (будущее)

Когда понадобится сервис флагов: контракт **GET /api/flags** (JSON), кэш на клиенте с TTL, fallback «всё выкл». Сейчас достаточно `WRA_*` в API и `NEXT_PUBLIC_FEATURE_*` во фронте (см. таблицу выше).
