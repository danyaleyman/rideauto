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

## Next.js (`web`)

- **Стек:** страницы `/`, `/catalog`, `/car/[id]` на Next.js 15 (SSR для метаданных и первого HTML; каталог гидрируется на клиенте; карточка авто подтягивает легаси `car-page.js` и статику из `frontend/` через `web/scripts/sync-legacy-assets.mjs`).
- **Данные:** поиск и фасеты — FastAPI + Meilisearch; карточка и гидратация — **PostgreSQL** (и Redis-кэш при настройке), не «старый» один только SQLite, если у вас в проде задан `WRA_PG_DSN`.
- **Сборка Docker:** контекст сборки образа `web` — **корень репозитория** (`docker-compose.yml`: `context: .`, `dockerfile: web/Dockerfile`); в образ копируется `frontend/` для sync в `public/` перед `next build`.
- **Прокси API:** в `next.config.ts` запросы браузера к `/api/*` на origin Next проксируются на `WRA_API_INTERNAL` (в compose по умолчанию `http://api:8080`). За **nginx** чаще `/api/` отдают сразу на uvicorn — тогда rewrite Next не используется, это нормально.
- **Редирект:** с Next приходит постоянный редирект **`/detail/:id` → `/car/:id`**. Если nginx по-прежнему отдаёт статический `car.html` на `/detail/`, настройте там **301 на `/car/`** или прокси на Next, чтобы не было дубля. Пример для nginx (если запросы к `/detail/` не попадают в Next):

```nginx
location ~ ^/detail/([^/]+)/?$ {
    return 301 /car/$1;
}
```
- **Переменные:** `NEXT_PUBLIC_API_BASE` (браузер), `WRA_API_INTERNAL` (SSR и rewrite при dev/standalone), **`NEXT_PUBLIC_SITE_URL`** (канонический домен для SEO, например `https://rideauto.ru`).

## Docker (опционально)

Из корня репозитория:

```bash
docker compose build
docker compose up -d
```

В томе `encar_data` лежат два каталога: **`/data/encar_cars.db`** (Корея / Encar) и **`/data/encar_china.db`** (Китай / Dongchedi). Переменная **`WRA_CHINA_DB_PATH`** в `docker-compose.yml` по умолчанию указывает на `/data/encar_china.db`. Чтобы подставить файлы с хоста, смонтируйте оба, например: `./encar_cars.db:/data/encar_cars.db` и `./encar_china.db:/data/encar_china.db`.

См. также [BACKUP-SQLITE.md](BACKUP-SQLITE.md).

## Китайский каталог (Dongchedi, отдельная SQLite)

Корейский каталог остаётся в **`encar_cars.db`** (аргумент **`--db`**). Китайский — в отдельном файле, чтобы не смешивать выдачу.

- Скрапер: из `backend/` выполните `python -m dongchedi.scraper --config dongchedi_scraper.yaml` (в YAML по умолчанию **`db_path: encar_china.db`** в каталоге `backend/`). На сервере задайте **`--db /opt/prod-encar/encar_china.db`**, чтобы путь совпадал с API. При обрыве прогона повторите с **`--resume`**: читается **`encar_china.scraper.checkpoint.json`** рядом с БД (номер shard и страницы листинга); после успешного окончания файл удаляется.
- Расписание: **`deploy/systemd/dongchedi-update.timer`** (или **`prod-dongchedi-update.timer`**) — **00:00 Asia/Yekaterinburg**, как **`encar-update.timer`**. Сначала один раз полный прогон вручную, затем включите timer.
- API: задайте **`WRA_CHINA_DB_PATH`** / **`--db-china`**, либо положите **`encar_china.db` в ту же папку, что и `encar_cars.db`**, или в **`backend/encar_china.db`** — тогда `api_server` подхватит файл сам. Проверка: **`GET /api/health`** → **`china_catalog_db": true`**. После первой выгрузки перезапустите API; при кэше nginx для `/api/cars` может понадобиться сброс зоны или ждать TTL.

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

### SEO-посадки марка/модель (пререндер)

Источник данных — `frontend/data/seo-landings.json`. Сгенерировать HTML и обновить блок URL в `frontend/sitemap-pages.xml`:

```bash
npm run generate:seo-landings
```

Файлы появляются в `frontend/seo/korea/<марка>/<модель>/index.html`. В nginx нужен префикс **`location ^~ /seo/korea/`** (см. `deploy/nginx/prod-encar.conf`). После деплоя перезагрузите nginx при изменении конфига.

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
