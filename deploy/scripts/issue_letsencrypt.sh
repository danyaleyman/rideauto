#!/usr/bin/env bash
# Выпуск Let's Encrypt для rideauto.ru.
#
# HTTP-01 с этого VPS часто падает на secondary validation Let's Encrypt
# (таймаут с запасных точек проверки — геофильтр хостера, не ufw).
# Если HTTP-01 снова Timeout — задайте REGRU_USERNAME + REGRU_PASSWORD
# (API reg.ru) и запустите с --dns.
set -euo pipefail
EMAIL="${LETSENCRYPT_EMAIL:-danyaleyman@yandex.ru}"
WEBROOT=/var/www/letsencrypt
mkdir -p "${WEBROOT}/.well-known/acme-challenge"

if [[ "${1:-}" == "--dns" ]]; then
  if [[ -z "${REGRU_USERNAME:-}" || -z "${REGRU_PASSWORD:-}" ]]; then
    echo "Нужны REGRU_USERNAME и REGRU_PASSWORD в env (API reg.ru)." >&2
    exit 2
  fi
  if ! command -v acme.sh >/dev/null 2>&1 && [[ ! -x /root/.acme.sh/acme.sh ]]; then
    curl -sS https://get.acme.sh | sh -s email="$EMAIL"
  fi
  export REGRU_API_Username="$REGRU_USERNAME"
  export REGRU_API_Password="$REGRU_PASSWORD"
  /root/.acme.sh/acme.sh --issue --dns dns_regru \
    -d rideauto.ru -d www.rideauto.ru \
    --server letsencrypt
  /root/.acme.sh/acme.sh --install-cert -d rideauto.ru \
    --key-file /etc/letsencrypt/live/rideauto.ru/privkey.pem \
    --fullchain-file /etc/letsencrypt/live/rideauto.ru/fullchain.pem \
    --reloadcmd "nginx -t && systemctl reload nginx"
  exit 0
fi

certbot certonly --webroot -w "$WEBROOT" \
  -d rideauto.ru -d www.rideauto.ru \
  --non-interactive --agree-tos --email "$EMAIL"
certbot install --nginx -d rideauto.ru -d www.rideauto.ru \
  --non-interactive --redirect
nginx -t && systemctl reload nginx
