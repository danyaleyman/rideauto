# Production deploy (Ubuntu + systemd + nginx) — rideauto.ru

## Безопасность

- **Токен Telegram-бота** держите только на сервере (`/etc/default/prod-encar`, права `600`). Не коммитьте и не отправляйте в чаты. Если токен засветился — в @BotFather перевыпустите (`/revoke` или новый токен).
- `SUBSCRIPTIONS_ADMIN_KEY` — длинная случайная строка для вызова `/api/subscriptions/run-notifications` из cron/systemd.

## DNS

У регистратора домена `rideauto.ru` укажите **A-запись** на IP вашего VPS (и при необходимости **www** → тот же IP или CNAME на основной хост).

## 1) Prepare server

```bash
sudo apt update
sudo apt install -y python3 python3-venv nginx certbot python3-certbot-nginx
sudo mkdir -p /opt/prod-encar
sudo chown -R $USER:$USER /opt/prod-encar
```

Залейте проект в `/opt/prod-encar`.

## 2) Python env

```bash
cd /opt/prod-encar
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## 3) systemd units

API и ночные задачи rideauto — юниты **`prod-encar-*`** в `deploy/systemd/`. Encar-каталог (Korea Postgres): **только** `prod-encar-auto-update` — установка и снятие дубликата `encar-update`:

```bash
sudo chmod +x deploy/scripts/prod_encar_catalog_install.sh
sudo bash deploy/scripts/prod_encar_catalog_install.sh
```

Остальное (пример):

```bash
sudo cp deploy/systemd/prod-encar-api.service /etc/systemd/system/
sudo cp deploy/systemd/prod-encar-subscriptions-notify.service /etc/systemd/system/
sudo cp deploy/systemd/prod-encar-subscriptions-notify.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now prod-encar-api.service
sudo systemctl enable --now prod-encar-subscriptions-notify.timer
```

Проверка:

```bash
systemctl status prod-encar-api.service
systemctl status prod-encar-auto-update.timer
systemctl status prod-encar-subscriptions-notify.timer
```

### Переменные API (Telegram-вход, избранное, подписки)

Пример переменных — в `deploy/env.prod-encar.example`. На сервере:

```bash
sudo nano /etc/default/prod-encar
```

Содержимое (подставьте свои значения):

```bash
TELEGRAM_BOT_TOKEN=ВАШ_НОВЫЙ_ТОКЕН_ИЗ_BOTFATHER
SUBSCRIPTIONS_ADMIN_KEY=длинная_случайная_строка
PUBLIC_SITE_URL=https://rideauto.ru
```

```bash
sudo chmod 600 /etc/default/prod-encar
sudo systemctl daemon-reload
sudo systemctl restart prod-encar-api.service
```

Сервисы **`prod-encar-api`** и **`prod-encar-subscriptions-notify`** читают этот файл (`EnvironmentFile=-/etc/default/prod-encar`).

### Telegram Login (виджет «Войти через Telegram»)

1. В @BotFather у вашего бота включите **Login** и укажите домен **`rideauto.ru`** (без `https://`).
2. Виджет на сайте использует **username бота** (без `@`). Задайте его в `web/public/js/wra-site-config.js` или переопределите до загрузки скрипта: `window.WRA_TELEGRAM_LOGIN_BOT = 'my_bot_username';`
3. **HTTPS обязателен** для реального входа — сначала получите сертификат (шаг ниже).

## 4) nginx

Для продакшена с **micro-cache** публичного API (`/api/cars`, `/api/facets`, …) и **без кэша** для сессионных маршрутов (`/api/me`, `/api/favorites`, …) используйте **`deploy/nginx/prod-encar.conf`**. В нём отдельные префиксные `location`; nginx выбирает **самый длинный** совпадающий префикс, поэтому персональные пути объявлены явно.

1. Один раз в **`http { }`** файла `/etc/nginx/nginx.conf` добавьте строку из комментария в `deploy/nginx/http_snippet_proxy_cache.conf` (`proxy_cache_path … keys_zone=prod_encar_api …`) и создайте каталог кэша:

   ```bash
   sudo mkdir -p /var/cache/nginx/prod-encar
   sudo chown -R www-data:www-data /var/cache/nginx/prod-encar
   ```

2. Подключите сайт:

   ```bash
   sudo cp deploy/nginx/prod-encar.conf /etc/nginx/sites-available/prod-encar.conf
   sudo ln -sf /etc/nginx/sites-available/prod-encar.conf /etc/nginx/sites-enabled/prod-encar.conf
   sudo nginx -t && sudo systemctl reload nginx
   ```

Упрощённый вариант без proxy_cache: `deploy/nginx/encar.conf`.

### HTTPS (Let’s Encrypt)

```bash
sudo certbot --nginx -d rideauto.ru -d www.rideauto.ru
```

Certbot допишет `listen 443 ssl` и пути к сертификатам. Затем снова:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Убедитесь, что `PUBLIC_SITE_URL` в `/etc/default/prod-encar` совпадает с публичным URL (**https://**).

## Пайплайн Encar (Postgres + Next + FastAPI)

Целевой продакшен — **PostgreSQL**; без доступного Postgres **`auto_update.py`** завершается ошибкой.

1. **Первый раз** — полная выгрузка (**`for`** + **`kor`**). В `scraper_config.yaml`: `storage.backend: postgres`, DSN / `DATABASE_URL`, `car_types: [for, kor]`, **`max_cars: 0`**. Команда:
   ```bash
   chmod +x deploy/scripts/first_full_encar_import.sh
   ./deploy/scripts/first_full_encar_import.sh /opt/prod-encar
   ```
   Либо: `.venv/bin/python backend/encar_scraper.py --config scraper_config.yaml`. Затем при необходимости **`postgres_catalog_sync`**, обновление **Meilisearch**.

2. **Каждый день 00:00 Asia/Yekaterinburg** — **`prod-encar-auto-update.timer`** → **`encar_daily_update.py --once`** (новые объявления, sold, **`encar_scraper --only-pending`**, при необходимости export в фронт по конфигу). Отдельный устаревший **`encar-update`** из репозитория убран — не включайте дубликаты.

3. **Сайт** — Next (`web/`); **API** — FastAPI, Postgres + Meilisearch. Китай — `dongchedi.scraper` в ту же БД; **`dongchedi-update.timer`**. Микрокэш nginx для **`/api/cars`** может отдавать устаревший ответ до ~60 s.

Если systemd не знает `Asia/Yekaterinburg` в `OnCalendar`, либо обновите systemd, либо задайте UTC-эквивалент: **00:00 Екатеринбурга (UTC+5) = 19:00 UTC предыдущего календарного дня** (запись вида `OnCalendar=*-*-* 19:00:00` в **UTC** требует сдвига при переходе ЛО‑времени — предпочтительно починить timezone в таймере).

## 5) Права на файлы

`encar-api.service` работает от `www-data` и нуждается в доступе к каталогу репозитория и переменным с DSN Postgres (`ReadWritePaths=/opt/prod-encar`). Локальные `*.db` на диске могут остаться только после миграции. Удобно: `deploy/scripts/ensure_scraper_runtime_permissions.sh` (логи + опциональные файлы).

Для **`prod-encar-auto-update`** / ручного `encar_daily_update` от **`prod-encar`**:

```bash
sudo WRA_RUNTIME_USER=prod-encar WRA_RUNTIME_GROUP=prod-encar bash /opt/prod-encar/deploy/scripts/ensure_scraper_runtime_permissions.sh
```

Если **`pip install`** в **`/opt/prod-encar/.venv`** от **`prod-encar`** падает с **`Permission denied`** в `site-packages` — каталог `.venv` частично принадлежит **root** (после случайного `sudo pip`) или осталась **полуустановленная** `hangul_romanize`. Скрипт прав (**от root**) снимает такие каталоги, делает **`chown`** и **`chmod u+rwX`** на весь `.venv`:

```bash
sudo WRA_RUNTIME_USER=prod-encar WRA_RUNTIME_GROUP=prod-encar WRA_CHOWN_VENV=1 bash /opt/prod-encar/deploy/scripts/ensure_scraper_runtime_permissions.sh
sudo -u prod-encar bash -c 'cd /opt/prod-encar && source .venv/bin/activate && pip install -r backend/requirements.txt'
```

Если ошибка повторяется, проверьте флаги неизменяемости: `lsattr -R /opt/prod-encar/.venv/lib/python3.10/site-packages/hangul_romanize 2>/dev/null | head` (не должно быть `i`/`a`). Снять: `sudo chattr -R -i` на проблемный путь (редко).

Иначе в логе будет: `cannot open log file ... Permission denied` (на работу скрейпера не влияет, если консольный лог ок).

### Git: «dubious ownership» и `could not lock ... /.gitconfig`

Если в `/etc/passwd` у пользователя **`prod-encar`** в поле **home** указано **`/opt/prod-encar`**, то **`git config --global`** пишет в **`/opt/prod-encar/.gitconfig`**. Каталог репозитория часто принадлежит **root** — получите **`Permission denied`** при любом глобальном `git config` от `prod-encar`.

**Правильно для прод-деплоя:** не использовать глобальный конфиг в корне репо. Скрипт **`deploy/scripts/encar_pull_kill_start.sh`** делает **`git pull` от root** и при необходимости добавляет **`safe.directory` только в `.git/config` репозитория** (локально), без `~/.gitconfig` у `prod-encar`.

Если вручную тянете репозиторий от **`prod-encar`**, используйте реальный домашний каталог (чтобы global был в **`/home/prod-encar/.gitconfig`**), например:

```bash
sudo install -d -o prod-encar -g prod-encar /home/prod-encar
sudo -u prod-encar env HOME=/home/prod-encar git -C /opt/prod-encar config --global --add safe.directory /opt/prod-encar
sudo -u prod-encar env HOME=/home/prod-encar git -C /opt/prod-encar pull origin main
```

Либо тяните от **root**, как в скрипте выше.

### Ручной прогон Encar daily (без копирования DSN в командную строку)

Реальный пароль к Postgres должен быть только в **`/etc/default/prod-encar`** (`DATABASE_URL` или `WRA_PG_DSN`). **Не подставляйте** строку вида `postgresql://USER:PASS@...` из примеров в чате — иначе Postgres попытается залогинить пользователя буквально **`USER`**.

```bash
sudo chmod +x /opt/prod-encar/deploy/scripts/run_encar_daily_once_prod.sh
sudo -u prod-encar /opt/prod-encar/deploy/scripts/run_encar_daily_once_prod.sh
```

Скрипт подхватывает env-файл, выставляет `DATABASE_URL` из `WRA_PG_DSN` при необходимости и запускает `encar_daily_update.py --once`. Конфиг по умолчанию — `scraper_config.yaml`; разовый тест на 20 новых INSERT: `WRA_SCRAPER_CONFIG=/opt/prod-encar/deploy/scraper_config.probe-20.yaml` только в командной строке (не класть в `/etc/default`, иначе заденет systemd).

### Только `postgres_catalog_sync` (без полного daily)

В `scraper_config.yaml` DSN часто пустой — синк тогда использует **`DATABASE_URL`** / **`WRA_PG_DSN`** / **`SYNC_PG_DSN`** из **`/etc/default/prod-encar`** (как скрипт Meilisearch):

```bash
sudo chmod +x /opt/prod-encar/deploy/scripts/run_postgres_catalog_sync_host.sh
sudo -u prod-encar bash /opt/prod-encar/deploy/scripts/run_postgres_catalog_sync_host.sh
```

Опции модуля в конец, например: `... run_postgres_catalog_sync_host.sh --no-meilisearch`.

После `git pull` с правками Python для API перезапустите активный unit (на проде из репозитория обычно **`prod-encar-api.service`**; если ставили вручную — может быть **`encar-api.service`**):  
`systemctl list-units --type=service --all | grep -E 'encar-api|prod-encar-api'` → затем `sudo systemctl restart имя.service`.

Прокси Encar (без правок YAML на сервере): в **`/etc/default/prod-encar`** задайте **`ENCAR_PROXY_URLS`** или выполните **`deploy/scripts/encar_set_proxy_urls.sh`** (секреты не попадают в git). Формат: `http://user:pass@host:port` через запятую. **`prod-encar-auto-update.service`** уже подключает `EnvironmentFile=-/etc/default/prod-encar` — после записи файла достаточно перезапустить таймер/oneshot.

### Pull, остановить старый encar и запустить новый прогон

Один скрипт от **root** (стоп unit/timer, `pkill` процессов `encar_scraper` / `encar_daily_update` от `prod-encar`, **`safe.directory` в локальном `.git/config`**, **`git pull` от root**, затем `run_encar_daily_once_prod.sh` от `prod-encar`):

```bash
sudo chmod +x /opt/prod-encar/deploy/scripts/encar_pull_kill_start.sh
sudo bash /opt/prod-encar/deploy/scripts/encar_pull_kill_start.sh
```

Те же шаги вручную:

```bash
sudo systemctl stop prod-encar-auto-update.service 2>/dev/null || true
sudo systemctl stop prod-encar-auto-update.timer 2>/dev/null || true
sudo pkill -u prod-encar -f '/opt/prod-encar/backend/encar_scraper.py' 2>/dev/null || true
sudo pkill -u prod-encar -f '/opt/prod-encar/backend/encar_daily_update.py' 2>/dev/null || true
sleep 2
git -C /opt/prod-encar config --local --get-all safe.directory 2>/dev/null | grep -Fxq /opt/prod-encar || \
  git -C /opt/prod-encar config --local --add safe.directory /opt/prod-encar
git -C /opt/prod-encar pull origin main
sudo -u prod-encar /opt/prod-encar/deploy/scripts/run_encar_daily_once_prod.sh
sudo systemctl start prod-encar-auto-update.timer
```

## 6) Verify

- Откройте `https://rideauto.ru/` — каталог.
- `https://rideauto.ru/api/health` → `{"status":"ok"}`.
- Войдите через Telegram на HTTPS-домене.

Ручной прогон обновления каталога:

```bash
cd /opt/prod-encar
source .venv/bin/activate
python backend/auto_update.py --config backend/config.json --type daily --workers 8
```

Опционально для CDN/отладки: **`postgres_catalog_sync --write-static-json`** пишет `web/public/cars.json` и чанки в `web/public/data/`. В проде листинг идёт через **API** + Meilisearch, а не через полный JSON.

## Sitemap на диск (~500k URL)

1. Каталог для генерации и путь в nginx (пример):

```bash
sudo mkdir -p /var/www/sitemap
sudo chown prod-encar:prod-encar /var/www/sitemap
```

2. В конфиге сайта уже есть блок `location /sitemap-gen/` → `alias /var/www/sitemap/;` (см. `deploy/nginx/prod-encar.conf`).

3. Таймер (обе БД обязательны):

```bash
sudo cp deploy/systemd/prod-encar-sitemap-gen.service /etc/systemd/system/
sudo cp deploy/systemd/prod-encar-sitemap-gen.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now prod-encar-sitemap-gen.timer
```

Проверка: `sudo systemctl start prod-encar-sitemap-gen.service` и откройте `https://ВАШ_ДОМЕН/sitemap-gen/sitemap-index.xml`.

4. В **Google Search Console** / `robots.txt` укажите основным индексом URL вида `https://rideauto.ru/sitemap-gen/sitemap-index.xml`.

## Прогрев кэша API после деплоя

```bash
cd /opt/prod-encar && .venv/bin/python scripts/warm_public_cache.py --base http://127.0.0.1:8080
```

(с localhost nginx проксирует на тот же воркер).

## Наблюдаемость

- Включите `WRA_PROMETHEUS_METRICS=1` в окружении API и снимайте `GET /api/metrics` (см. `deploy/env.prod-encar.example`): счётчики запросов, средняя и **p95** латентность для групп `cars`, `facets`, `car`.
- Алерты: рост `wra_http_request_duration_ms_p95{route_group="cars"}`, доля 429/503, **mtime** файлов в `/var/www/sitemap`, размер `encar_*.db` и `*-wal` на диске (`GET /api/health?deep=1`).

## Примечания

- Пути `User/Group` и `/opt/prod-encar` в `deploy/systemd/*.service` при необходимости поменяйте под свой сервер.
- Таймер уведомлений по подпискам по умолчанию — каждые 10 минут (`encar-subscriptions-notify.timer`).

