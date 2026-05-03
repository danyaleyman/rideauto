# Деплой API (rideauto)

## Один systemd-юнит на порт

На одном сервере и одном порту должен работать **только один** экземпляр API. Если когда-то ставили и `encar-api.service`, и `rideauto-api.service`, оставьте один юнит и отключите второй:

```bash
sudo systemctl disable --now rideauto-api.service   # или encar-api — тот, который дублирует порт
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

- **Публичный сайт:** Next.js 15 — **`/`**, **`/catalog`**, **`/car/[id]`**, **`/about`**, **`/contacts`**, **`/buy`**, **`/privacy`**, **`/cookies`**, **`/agreement`**. Nginx проксирует **`/`** и эти пути на процесс Next (см. **`deploy/nginx/nextjs-frontend.snippet.conf`**). В `@wra_extensionless` уберите **`rewrite ^/catalog$ /index.html`**, если осталось от старой статики.
- **Данные:** Meilisearch + FastAPI; в проде с **`WRA_PG_DSN`** — **PostgreSQL** (каталог и карточки).
- **Сборка:** `sync-static-data.mjs` копирует JSON-справочники (`engine_map.json`, `encar_mapping.json`) в `web/public/data`. Docker образ `web`: контекст **корень репозитория**, см. `web/Dockerfile`.
- **Прокси API:** на origin Next `/api/*` → `WRA_API_INTERNAL`; у вас на nginx `/api/` может идти сразу на uvicorn — ок.
- **Редиректы в Next:** `/index.html` → `/`, `/*.html` → каноника, `/detail/:id` → `/car/:id`. На nginx для `/detail/`: `return 301 /car/$1` или прокси на Next.

```nginx
location ~ ^/detail/([^/]+)/?$ {
    return 301 /car/$1;
}
```

- **Переменные:** `WRA_API_INTERNAL`, **`NEXT_PUBLIC_SITE_URL`**, опционально **`NEXT_PUBLIC_API_BASE`**.
- **Пустой `NEXT_PUBLIC_API_BASE` (рекомендуется для Docker и одного домена):** браузер вызывает `/api/...` на том же origin, Next проксирует на `WRA_API_INTERNAL`. Так каталог работает при открытии сайта по `http://IP:3000`, а не только с `localhost`.
- **Важно для Docker:** `NEXT_PUBLIC_*` подставляются на этапе **`docker compose build web`** (см. `web/Dockerfile` и `build.args` в `docker-compose.yml`). После смены публичного URL в `.env` выполните **`docker compose build web`** и **`docker compose up -d web`**.

### Чеклист: прод (один домен, nginx → Next + API)

1. **`.env`** на сервере (пример для `https://rideauto.ru`, API снаружи только через nginx):

   ```env
   WRA_API_INTERNAL=http://api:8080
   NEXT_PUBLIC_SITE_URL=https://rideauto.ru
   # NEXT_PUBLIC_API_BASE=   — пусто: браузер → https://rideauto.ru/api/... (через Next или nginx)
   # либо явно: NEXT_PUBLIC_API_BASE=https://rideauto.ru
   ```

   Браузер ходит на `https://rideauto.ru/api/...`; nginx, как в **`deploy/nginx/rideauto.conf`**, может проксировать `/api/` сразу на **`127.0.0.1:8080`** или на Next — оба варианта совместимы с пустым `NEXT_PUBLIC_API_BASE`.

2. **Пересобрать и поднять `web`** после правок `NEXT_PUBLIC_*`:

   ```bash
   cd /opt/rideauto
   docker compose build web
   docker compose up -d web
   ```

3. **Nginx:** включить маршруты из **`deploy/nginx/nextjs-frontend.snippet.conf`** *выше* общего `location /` и `location = /` в **`rideauto.conf`**: закомментировать старый `location = /` с `try_files /index.html` и вставить сниппет; в **`location @wra_extensionless`** убрать `rewrite ^/catalog$ /index.html`. Те же `location` продублировать в `server { listen 443 ssl; }`. См. комментарии в сниппете и **`TROUBLESHOOT-HTTPS.txt`**.

4. **Дым с сервера** (подставьте домен):

   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" "https://rideauto.ru/api/health"
   curl -sS -o /dev/null -w "%{http_code}\n" "https://rideauto.ru/"
   curl -sS -o /dev/null -w "%{http_code}\n" "https://rideauto.ru/catalog"
   ```

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
cd /opt/rideauto
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

Должно показать что-то вроде `Docker Compose version v2.x.x`. Дальше из `/opt/rideauto` используйте **`docker compose`** вместо **`docker-compose`**:

```bash
docker compose ps
docker compose build api web
docker compose up -d api web
```

Старый бинарник **`docker-compose`** (v1) можно оставить или удалить пакетом `docker-compose` из репозитория Ubuntu, если он ставился отдельно — на работу **`docker compose`** это не влияет.

Рабочий каталог — **PostgreSQL** (том `postgres` / `DATABASE_URL`).

## Cutover + Rollback (после миграции БД)

### Cutover checklist

1. Подтянуть актуальный код и поднять сервисы:

```bash
cd /opt/rideauto
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
cd /opt/rideauto
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

## Китайский каталог (Dongchedi, Postgres)

И Корея, и Китай лежат в **одной** базе Postgres (различаются полями `source` / регион в JSON).

- Скрапер: из `backend/` выполните `python -m dongchedi.scraper --config dongchedi_scraper.yaml` (в YAML — `storage.postgres.dsn` или `DATABASE_URL`; `db_path` — только префикс имени **checkpoint**-файла рядом с репо). При обрыве: **`--resume`** и тот же `db_path`.
- Расписание: **`deploy/systemd/dongchedi-update.timer`** (или **`prod-dongchedi-update.timer`**) — **00:00 Asia/Yekaterinburg**, как **`rideauto-auto-update.timer`**. Сначала один раз полный прогон вручную, затем включите timer.
- API: **FastAPI** читает Postgres и Meilisearch; отдельный `WRA_CHINA_DB_PATH` для каталога не требуется. После прогона при необходимости обновите индекс Meilisearch и сбросьте кэш nginx для `/api/*`.

### Ночное обновление не сработало — диагностика и ручной запуск

- Логи systemd: `bash deploy/scripts/diagnose_nightly_updates.sh` или вручную `journalctl -u rideauto-auto-update.service -n 150` и `journalctl -u dongchedi-update.service -n 150`.
- Частая причина по Корее: **`rideauto-auto-update.service`** запускает **`encar_daily_update.py --once`**; при **ненулевом коде** юнит падает — смотрите `journalctl -u rideauto-auto-update.service`.
- Если в логе **`password authentication failed for user "postgres"`** — без рабочего Postgres ночной цикл Encar не выполнится. Проверьте `db_config` в **`backend/config.json`** и `DATABASE_URL` у скрапера.
- Корея вручную (discover + pending): **`sudo bash deploy/scripts/run_korea_encar_daily_once.sh`** из корня репо. **`auto_learn_engine_map`** после sync не запускается, пока не задано **`WRA_LEARN_ENGINE_MAP=1`** в env.
- Китай полный перескрейп: остановите таймер Dongchedi, затем **`bash deploy/scripts/run_china_dongchedi_full_rescrape.sh`**.
- Китай **тест одной страницы**: **`sudo bash deploy/scripts/run_china_dongchedi_test_one_page.sh`** из `/opt/rideauto` (лимит: **`CHINA_TEST_LIMIT=12`** и т.д.). Потом обновите Meilisearch и проверьте каталог **`?region=china`**.

## Заголовки безопасности (nginx)

Пример готовых директив: [nginx-security-headers.example.conf](nginx-security-headers.example.conf).

Для проксирования **`/api/`** на uvicorn/FastAPI задайте запас по времени (иначе при тяжёлом первом запросе клиент увидит обрыв ~50–60 с). Пример:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_read_timeout 120s;
    proxy_connect_timeout 10s;
    proxy_send_timeout 120s;
}
```

## Статика фронтенда (Next + public)

Статические ассеты раздаёт Next из **`web/public`** (`/image/*`, `/data/*`, `/seo/*`, …).

### SEO-посадки марка/модель (пререндер)

Источник данных — `data/seo-landings.json`. Сгенерировать HTML и обновить блок URL в `web/public/sitemap-pages.xml`:

```bash
npm run generate:seo-landings
```

Файлы появляются в `web/public/seo/korea/<марка>/<модель>/index.html`. В nginx нужен префикс **`location ^~ /seo/korea/`** (см. `deploy/nginx/rideauto.conf`).

## Версии query-параметра `?v=` у JS/CSS

При релизе обновляйте суффикс `?v=` у изменённых статических файлов (или используйте `scripts/bump-asset-version.mjs` из корня репозитория), иначе у клиентов останется старый кэш.

## Логи и лимиты API

- Уровень логирования uvicorn задаётся флагами запуска / переменными окружения (см. unit systemd для API). Для распределённой трассировки можно использовать стандартные заголовки прокси.
- **`WRA_RATE_LIMIT_POST_PER_MINUTE`** — лимит **POST** на IP за скользящее окно 60 с. `0` или не задано — **без лимита**. За IP при работе за nginx берётся первый адрес из **`X-Forwarded-For`**, иначе `request.remote`.
- **`WRA_RATE_LIMIT_TELEGRAM_AUTH_PER_MINUTE`** — отдельный лимит только для **`POST /api/auth/telegram`** (если > 0). При превышении ответ **429** и JSON `{"error":"rate_limit"}`, заголовок **`Retry-After: 60`**.

## Каталог: `ERR_CONNECTION_TIMED_OUT` к `/api/cars`

**`curl http://127.0.0.1:8080/api/health` с сервера** проверяет только процесс API. Браузер ходит на **ваш домен по HTTPS** — туда должен попасть **тот же** upstream через nginx.

### 1. Проверка «как браузер» (с сервера)

Подставьте свой домен и схему:

```bash
curl -sS -m 15 -o /dev/null -w "%{http_code}\n" "https://ВАШ-ДОМЕН/api/health"
curl -sS -m 60 "https://ВАШ-ДОМЕН/api/cars?page=1&per_page=2&source=encar" | head -c 200
```

Если здесь таймаут или не JSON — проблема в **nginx (443)** или CDN, а не в Python.

### 2. Частая ошибка: в `server { listen 443 ssl; }` нет `location /api/`

Certbot добавляет отдельный блок для HTTPS. Если туда **не скопированы** все `location /api/...` из [deploy/nginx/rideauto.conf](nginx/rideauto.conf), то запросы к `https://сайт/api/cars` попадают в `location /` и отдаются как статика (или 404) — в DevTools это часто выглядит как **долгий pending / timeout**.

См. также [deploy/nginx/TROUBLESHOOT-HTTPS.txt](nginx/TROUBLESHOOT-HTTPS.txt).

### 3. Локальный API и прокси

1. `curl -sS -m 5 http://127.0.0.1:8080/api/health` — `{"status":"ok"}`.
2. В активном `server{}` для сайта (в т.ч. **443**) есть `proxy_pass` на этот порт для `/api/`.
3. Если на фронте задан **`window.WRA_API_BASE`** на другой хост — он должен открываться из браузера пользователя.

### 4. Кэш nginx

В `rideauto.conf` для каталога включён `proxy_cache_lock`. Если первый запрос к upstream «висит», остальные ждут замка. В актуальной версии конфига задан **`proxy_cache_lock_timeout 20s`**, чтобы запросы не копились бесконечно. После `git pull` перенесите эти строки в свой реальный `sites-enabled`.


