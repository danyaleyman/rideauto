# Production deploy (Ubuntu + systemd + nginx)

## 1) Prepare server

```bash
sudo apt update
sudo apt install -y python3 python3-venv nginx
sudo mkdir -p /opt/prod-encar
sudo chown -R $USER:$USER /opt/prod-encar
```

Upload project to `/opt/prod-encar`.

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
sudo systemctl daemon-reload
sudo systemctl enable --now encar-api.service
sudo systemctl enable --now encar-update.timer
```

Check:

```bash
systemctl status encar-api.service
systemctl status encar-update.timer
```

## 4) nginx

```bash
sudo cp deploy/nginx/encar.conf /etc/nginx/sites-available/encar.conf
sudo ln -sf /etc/nginx/sites-available/encar.conf /etc/nginx/sites-enabled/encar.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 5) Verify

- Open `http://SERVER_IP/` — catalog page
- Open `http://SERVER_IP/api/health` — should return `{"status":"ok"}`
- Run one update manually:

```bash
cd /opt/prod-encar
source .venv/bin/activate
python backend/auto_update.py --config backend/config.json --type daily --workers 8
```

After update:
- `frontend/cars.json`
- `frontend/data/cars.index.json`
- `frontend/data/chunks/cars_*.json`
- `.gz` variants

## 6) Домен www.wrideauto.ru

В репозитории: `deploy/nginx/prod-encar.conf` — `wrideauto.ru` редиректит на `www.wrideauto.ru`, статика из `/opt/prod-encar/frontend`, API на `127.0.0.1:8080`.

```bash
sudo cp deploy/nginx/prod-encar.conf /etc/nginx/sites-available/prod-encar.conf
sudo ln -sf /etc/nginx/sites-available/prod-encar.conf /etc/nginx/sites-enabled/prod-encar.conf
sudo nginx -t && sudo systemctl reload nginx
```

Карточка с отчётом: `https://www.wrideauto.ru/car.html?id=<ID>` (в каталоге «Поделиться» копирует этот URL; для локальной отладки можно задать `localStorage.encar_site_origin`).

### HTTPS (Certbot)

После того как DNS A-записи `@` и `www` указывают на IP сервера:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d www.wrideauto.ru -d wrideauto.ru
```

Certbot добавит `listen 443 ssl` и сертификаты; при необходимости обновите редирект apex → www на `https://`.

## 7) Опционально: отчёты бота по `/r/<token>`

Если на том же VPS крутится Telegram-бот с Flask `report_server` на порту, например `9090`:

1. В окружении бота: `REPORT_BASE_URL=https://www.wrideauto.ru` (и тот же порт, что в nginx).
2. В `prod-encar.conf` раскомментируйте блок `location /r/` и выставьте `proxy_pass` на нужный порт.

## Notes

- Adjust `User/Group` and paths in `deploy/systemd/*.service` for your server user.
- If using domain + TLS, add Certbot and HTTPS server block.
