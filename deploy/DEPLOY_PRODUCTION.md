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

```bash
sudo cp deploy/systemd/encar-api.service /etc/systemd/system/
sudo cp deploy/systemd/encar-update.service /etc/systemd/system/
sudo cp deploy/systemd/encar-update.timer /etc/systemd/system/
sudo cp deploy/systemd/encar-subscriptions-notify.service /etc/systemd/system/
sudo cp deploy/systemd/encar-subscriptions-notify.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now encar-api.service
sudo systemctl enable --now encar-update.timer
sudo systemctl enable --now encar-subscriptions-notify.timer
```

Проверка:

```bash
systemctl status encar-api.service
systemctl status encar-update.timer
systemctl status encar-subscriptions-notify.timer
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
sudo systemctl restart encar-api.service
```

Сервисы `encar-api` и `encar-subscriptions-notify` читают этот файл (`EnvironmentFile=-/etc/default/prod-encar`).

### Telegram Login (виджет «Войти через Telegram»)

1. В @BotFather у вашего бота включите **Login** и укажите домен **`rideauto.ru`** (без `https://`).
2. Виджет на сайте использует **username бота** (без `@`). Задайте его в `frontend/js/wra-site-config.js` (поле по умолчанию можно заменить на username нового бота) или переопределите до загрузки скрипта: `window.WRA_TELEGRAM_LOGIN_BOT = 'my_bot_username';`
3. **HTTPS обязателен** для реального входа — сначала получите сертификат (шаг ниже).

## 4) nginx

Используйте `deploy/nginx/encar.conf` или `deploy/nginx/prod-encar.conf` (оба настроены под `rideauto.ru` и `www.rideauto.ru`).

```bash
sudo cp deploy/nginx/encar.conf /etc/nginx/sites-available/encar.conf
sudo ln -sf /etc/nginx/sites-available/encar.conf /etc/nginx/sites-enabled/encar.conf
sudo nginx -t
sudo systemctl reload nginx
```

### HTTPS (Let’s Encrypt)

```bash
sudo certbot --nginx -d rideauto.ru -d www.rideauto.ru
```

Certbot допишет `listen 443 ssl` и пути к сертификатам. Затем снова:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Убедитесь, что `PUBLIC_SITE_URL` в `/etc/default/prod-encar` совпадает с публичным URL (**https://**).

## Пайплайн Encar (как всё крутится без ручных нажатий)

Продакшен без PostgreSQL использует **SQLite** (`encar_cars.db`) и `backend/config.json` с недоступным Postgres — тогда `auto_update.py` вызывает **`encar_daily_update.py --once`**.

1. **Первый раз на сервере** — полная выгрузка каталога (импорт **`for`** + местные **`kor`**, как две вкладки на encar.com). В `scraper_config.yaml`: `car_types: [for, kor]`, **`max_cars: 0`** (без лимита). Команда:
   ```bash
   chmod +x deploy/scripts/first_full_encar_import.sh
   ./deploy/scripts/first_full_encar_import.sh /opt/prod-encar
   ```
   Либо вручную: `.venv/bin/python backend/encar_scraper.py --config scraper_config.yaml`. В конце скрапер сам вызывает экспорт в `frontend/` (**`export_from_scraper_db.py`**, внутри — **`price.py`**, курсы Binance и поля `my_price` и т.д.).

2. **Каждый день в 12:00 Asia/Yekaterinburg** срабатывает **`encar-update.timer`** → **`encar-update.service`** → **`auto_update.py --type daily`**. Цикл SQLite:
   - новые объявления по свежим страницам списка **for/kor**;
   - выборка из БД → проверка «продан» (404 и т.п.) → удаление;
   - догрузка деталей по очереди `--only-pending`;
   - снова **экспорт + расчёт цен** (тот же `export_from_scraper_db`, отдельно **`price.py`** не вызывать).

3. **Сайт** отдаёт статику из `frontend/`; **API** (`encar-api`) читает ту же БД — каталог и карточки с актуальными ценами после шага 2.

Если ваш systemd старый и не понимает `Asia/Yekaterinburg` в `OnCalendar`, задайте эквивалент в UTC (**07:00 UTC** = 12:00 Екатеринбург зимой) или включите нужный timezone на хосте и упростите запись таймера.

## 5) Права на файлы

`encar-api.service` работает от `www-data` и нуждается в чтении/записи БД и каталога проекта (`ReadWritePaths=/opt/prod-encar`). Выдайте права на `encar_cars.db` и при необходимости на `frontend/` так, чтобы `www-data` мог обновлять артефакты скрапера (или запускайте обновление каталога от того же пользователя).

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

После обновления появляются/обновляются:

- `frontend/cars.json`
- `frontend/data/cars.index.json`
- `frontend/data/chunks/cars_*.json`
- при необходимости `.gz` варианты

## Примечания

- Пути `User/Group` и `/opt/prod-encar` в `deploy/systemd/*.service` при необходимости поменяйте под свой сервер.
- Таймер уведомлений по подпискам по умолчанию — каждые 10 минут (`encar-subscriptions-notify.timer`).
