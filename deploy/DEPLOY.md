# Деплой API (prod-encar)

## Один systemd-юнит на порт

На одном сервере и одном порту должен работать **только один** экземпляр API. Если когда-то ставили и `encar-api.service`, и `prod-encar-api.service`, оставьте один юнит и отключите второй:

```bash
sudo systemctl disable --now prod-encar-api.service   # или encar-api — тот, который дублирует порт
sudo systemctl enable --now encar-api.service       # активный юнит
```

Проверка: `curl -sS http://127.0.0.1:<PORT>/api/health` и `curl -sS http://127.0.0.1:<PORT>/api/version`.

## Версия в ответах (`WRA_GIT_SHA`)

При деплое задайте переменную окружения **`WRA_GIT_SHA`** (или **`GIT_COMMIT`**) — короткий или полный SHA коммита. Тогда:

- `GET /api/version` всегда отдаёт `service`, `git_sha`, `python` (без кэша);
- `GET /api/health` при наличии SHA добавит поле `git_sha`.

Пример в `Environment=` в unit-файле см. `encar-api.service.example`.

## Nginx

Проксируйте префикс `/api/` на тот же upstream, что уже используется для каталога. Отдельный `location` для `/api/version` не обязателен.

## Docker (опционально)

Из корня репозитория:

```bash
docker compose build
docker compose up -d
```

По умолчанию БД в именованном томе `encar_data` по пути контейнера `/data/encar_cars.db`. Чтобы подставить свою БД с хоста, замените в `docker-compose.yml` секцию `volumes` у сервиса `api` на что-то вроде `./encar_cars.db:/data/encar_cars.db` (файл на хосте должен существовать или быть создан пустым перед первым запуском).

См. также [BACKUP-SQLITE.md](BACKUP-SQLITE.md).

## Заголовки безопасности (nginx)

Пример готовых директив: [nginx-security-headers.example.conf](nginx-security-headers.example.conf).

## Статика фронтенда

После выноса скрипта страницы авто убедитесь, что файл `frontend/js/car-page.js` отдаётся по пути `/js/car-page.js` (как и остальные `js/*`). Если подключён `car-page-dicts.js`, он должен идти **перед** `car-page.js`.

## Версии query-параметра `?v=` у JS/CSS

При релизе обновляйте суффикс `?v=` у изменённых статических файлов (или используйте `scripts/bump-asset-version.mjs` из корня репозитория), иначе у клиентов останется старый кэш.

## Логи и лимиты API

- **`LOG_LEVEL`** — уровень логирования при запуске `python -m api_server` (по умолчанию `INFO`). В лог пишется строка на запрос: метод, путь, статус, длительность, `rid` (совпадает с заголовком ответа **`X-Request-Id`**). Клиент может прислать свой `X-Request-Id` (8–64 символа, `[a-zA-Z0-9-]`).
- **`WRA_RATE_LIMIT_POST_PER_MINUTE`** — лимит **POST** на IP за скользящее окно 60 с. `0` или не задано — **без лимита**. За IP при работе за nginx берётся первый адрес из **`X-Forwarded-For`**, иначе `request.remote`.
- **`WRA_RATE_LIMIT_TELEGRAM_AUTH_PER_MINUTE`** — отдельный лимит только для **`POST /api/auth/telegram`** (если > 0). При превышении ответ **429** и JSON `{"error":"rate_limit"}`, заголовок **`Retry-After: 60`**.
