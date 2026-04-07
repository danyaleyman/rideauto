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

- **Публичный сайт:** Next.js 15 — **`/`**, **`/catalog`**, **`/car/[id]`**, **`/about`**, **`/contacts`**, **`/buy`** (iframe с легаси-калькулятором `howtobuy.html`), **`/privacy`**, **`/cookies`**, **`/agreement`**. Главная **больше не** `frontend/index.html` в проде: nginx проксирует **`/`** и перечисленные пути на процесс Next (см. **`deploy/nginx/nextjs-frontend.snippet.conf`**). В `@wra_extensionless` уберите **`rewrite ^/catalog$ /index.html`**.
- **Данные:** Meilisearch + FastAPI; в проде с **`WRA_PG_DSN`** — **PostgreSQL** (каталог и карточки), не только SQLite.
- **Сборка:** `sync-legacy-assets.mjs` зеркалирует статику, **`seo/`**, **`howtobuy.html`**, фрагменты **car**, **about/contacts**. Docker образ `web`: контекст **корень репозитория**, см. `web/Dockerfile`.
- **Прокси API:** на origin Next `/api/*` → `WRA_API_INTERNAL`; у вас на nginx `/api/` может идти сразу на uvicorn — ок.
- **Редиректы в Next:** `/index.html` → `/`, `/*.html` → каноника, `/detail/:id` → `/car/:id`. На nginx для `/detail/`: `return 301 /car/$1` или прокси на Next.

```nginx
location ~ ^/detail/([^/]+)/?$ {
    return 301 /car/$1;
}
```

- **Переменные:** `NEXT_PUBLIC_API_BASE`, `WRA_API_INTERNAL`, **`NEXT_PUBLIC_SITE_URL`**.

## Docker (опционально)

Из корня репозитория:

```bash
docker compose build
docker compose up -d
```

Сервис **`api`** собирается с контекстом **`backend/`** (не весь репозиторий), чтобы образ собирался быстро.

### docker-compose 1.29 + Docker Engine: `KeyError: 'ContainerConfig'`

Старый **`docker-compose`** (Python 1.29.x) при пересоздании контейнера иногда падает с этой ошибкой. Обход:

```bash
cd /opt/prod-encar
docker-compose rm -f api
docker-compose up -d api
```

Надёжнее поставить **[Compose V2](https://docs.docker.com/compose/install/linux/)** и вызывать **`docker compose`** (без дефиса).

### Установка Compose V2 на Ubuntu (plugin)

Нужен Docker из официального репозитория Docker (`apt` уже знает пакет `docker-compose-plugin`).

```bash
sudo apt-get update
sudo apt-get install -y docker-compose-plugin
docker compose version
```

Должно показать что-то вроде `Docker Compose version v2.x.x`. Дальше из `/opt/prod-encar` используйте **`docker compose`** вместо **`docker-compose`**:

```bash
docker compose ps
docker compose build api web
docker compose up -d api web
```

Старый бинарник **`docker-compose`** (v1) можно оставить или удалить пакетом `docker-compose` из репозитория Ubuntu, если он ставился отдельно — на работу **`docker compose`** это не влияет.

В томе `encar_data` лежат два каталога: **`/data/encar_cars.db`** (Корея / Encar) и **`/data/encar_china.db`** (Китай / Dongchedi). Переменная **`WRA_CHINA_DB_PATH`** в `docker-compose.yml` по умолчанию указывает на `/data/encar_china.db`. Чтобы подставить файлы с хоста, смонтируйте оба, например: `./encar_cars.db:/data/encar_cars.db` и `./encar_china.db:/data/encar_china.db`.

См. также [BACKUP-SQLITE.md](BACKUP-SQLITE.md).

## Cutover + Rollback (после миграции БД)

### Cutover checklist

1. Подтянуть актуальный код и поднять сервисы:

```bash
cd /opt/prod-encar
git fetch --all
git pull --ff-only
docker compose up -d --build api web
```

2. Проверить smoke:

```bash
curl -fsS "http://127.0.0.1:8080/api/health"
curl -fsS "http://127.0.0.1:8080/api/search?per_page=2" | head
curl -I "http://127.0.0.1:3000/catalog"
```

3. Прогнать пост-миграционную сверку:

```bash
chmod +x deploy/scripts/post_migration_check.sh
deploy/scripts/post_migration_check.sh
```

### Rollback (быстрый)

Если после релиза выросли 5xx/latency:

1. Вернуть предыдущий коммит:

```bash
cd /opt/prod-encar
git log --oneline -n 5
git checkout <PREVIOUS_GOOD_SHA>
```

2. Пересобрать и поднять только приложение:

```bash
docker compose up -d --build api web
```

3. Проверить health и поиск:

```bash
curl -fsS "http://127.0.0.1:8080/api/health"
curl -fsS "http://127.0.0.1:8080/api/search?per_page=2" | head
```

4. После стабилизации зафиксировать hotfix или вернуть `main` и повторить деплой.

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
