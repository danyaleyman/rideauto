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

Для проксирования **`/api/`** на aiohttp задайте запас по времени (иначе при тяжёлом первом запросе к SQLite или большой БД клиент увидит обрыв ~50–60 с). Пример:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_read_timeout 120s;
    proxy_connect_timeout 10s;
    proxy_send_timeout 120s;
}
```

## Статика фронтенда

После выноса скрипта страницы авто убедитесь, что файл `frontend/js/car-page.js` отдаётся по пути `/js/car-page.js` (как и остальные `js/*`). Если подключён `car-page-dicts.js`, он должен идти **перед** `car-page.js`.

## Версии query-параметра `?v=` у JS/CSS

При релизе обновляйте суффикс `?v=` у изменённых статических файлов (или используйте `scripts/bump-asset-version.mjs` из корня репозитория), иначе у клиентов останется старый кэш.

## Логи и лимиты API

- **`LOG_LEVEL`** — уровень логирования при запуске `python -m api_server` (по умолчанию `INFO`). В лог пишется строка на запрос: метод, путь, статус, длительность, `rid` (совпадает с заголовком ответа **`X-Request-Id`**). Клиент может прислать свой `X-Request-Id` (8–64 символа, `[a-zA-Z0-9-]`).
- **`WRA_RATE_LIMIT_POST_PER_MINUTE`** — лимит **POST** на IP за скользящее окно 60 с. `0` или не задано — **без лимита**. За IP при работе за nginx берётся первый адрес из **`X-Forwarded-For`**, иначе `request.remote`.
- **`WRA_RATE_LIMIT_TELEGRAM_AUTH_PER_MINUTE`** — отдельный лимит только для **`POST /api/auth/telegram`** (если > 0). При превышении ответ **429** и JSON `{"error":"rate_limit"}`, заголовок **`Retry-After: 60`**.

## Каталог: `ERR_CONNECTION_TIMED_OUT` к `/api/cars`

**`curl http://127.0.0.1:8080/api/health` с сервера** проверяет только процесс aiohttp. Браузер ходит на **ваш домен по HTTPS** — туда должен попасть **тот же** upstream через nginx.

### 1. Проверка «как браузер» (с сервера)

Подставьте свой домен и схему:

```bash
curl -sS -m 15 -o /dev/null -w "%{http_code}\n" "https://ВАШ-ДОМЕН/api/health"
curl -sS -m 60 "https://ВАШ-ДОМЕН/api/cars?page=1&per_page=2&source=encar" | head -c 200
```

Если здесь таймаут или не JSON — проблема в **nginx (443)** или CDN, а не в Python.

### 2. Частая ошибка: в `server { listen 443 ssl; }` нет `location /api/`

Certbot добавляет отдельный блок для HTTPS. Если туда **не скопированы** все `location /api/...` из [deploy/nginx/prod-encar.conf](nginx/prod-encar.conf), то запросы к `https://сайт/api/cars` попадают в `location /` и отдаются как статика (или 404) — в DevTools это часто выглядит как **долгий pending / timeout**.

См. также [deploy/nginx/TROUBLESHOOT-HTTPS.txt](nginx/TROUBLESHOOT-HTTPS.txt).

### 3. Локальный API и прокси

1. `curl -sS -m 5 http://127.0.0.1:8080/api/health` — `{"status":"ok"}`.
2. В активном `server{}` для сайта (в т.ч. **443**) есть `proxy_pass` на этот порт для `/api/`.
3. Если на фронте задан **`window.WRA_API_BASE`** на другой хост — он должен открываться из браузера пользователя.

### 4. Кэш nginx

В `prod-encar.conf` для каталога включён `proxy_cache_lock`. Если первый запрос к upstream «висит», остальные ждут замка. В актуальной версии конфига задан **`proxy_cache_lock_timeout 20s`**, чтобы запросы не копились бесконечно. После `git pull` перенесите эти строки в свой реальный `sites-enabled`.
