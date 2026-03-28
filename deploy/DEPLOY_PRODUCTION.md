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
sudo cp deploy/systemd/encar-subscriptions-notify.service /etc/systemd/system/
sudo cp deploy/systemd/encar-subscriptions-notify.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now encar-api.service
sudo systemctl enable --now encar-update.timer
sudo systemctl enable --now encar-subscriptions-notify.timer
```

Check:

```bash
systemctl status encar-api.service
systemctl status encar-update.timer
systemctl status encar-subscriptions-notify.timer
```

### API env vars (required for Telegram auth/subscriptions)

Create env file for systemd services:

```bash
sudo tee /etc/default/prod-encar >/dev/null <<'EOF'
TELEGRAM_BOT_TOKEN=123456:your_bot_token
SUBSCRIPTIONS_ADMIN_KEY=replace_with_long_random_secret
PUBLIC_SITE_URL=https://your-domain.com
EOF
sudo chmod 600 /etc/default/prod-encar
sudo systemctl daemon-reload
sudo systemctl restart encar-api.service
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

## Notes

- Adjust `User/Group` and paths in `deploy/systemd/*.service` for your server user.
- If using domain + TLS, add Certbot and HTTPS server block.
- Subscription notifications timer runs every 10 minutes by default (`encar-subscriptions-notify.timer`).
