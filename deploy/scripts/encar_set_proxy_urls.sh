#!/usr/bin/env bash
# Записать ENCAR_PROXY_URLS в defaults без хранения секретов в git.
# Юнит prod-encar-auto-update и run_encar_daily_once_prod.sh читают /etc/default/prod-encar.
#
# Пример (URL в одинарных кавычках — спецсимволы в пароле безопаснее):
#   sudo bash /opt/prod-encar/deploy/scripts/encar_set_proxy_urls.sh \
#     /etc/default/prod-encar 'http://LOGIN:PASSWORD@geo.floppydata.com:10080'
#
# Для encar-update (www-data) и файла prod-encar-scrapers:
#   sudo bash .../encar_set_proxy_urls.sh /etc/default/prod-encar-scrapers 'http://...' www-data
set -euo pipefail
ENV_FILE="${1:?первый аргумент: путь, например /etc/default/prod-encar}"
PROXY_URL="${2:?второй аргумент: полный URL http://user:pass@host:port}"
GROUP="${3:-prod-encar}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root: sudo bash $0 ..." >&2
  exit 1
fi

tmp="$(mktemp)"
if [[ -f "$ENV_FILE" ]]; then
  grep -v '^[[:space:]]*ENCAR_PROXY_URLS=' "$ENV_FILE" >"$tmp" || true
else
  printf '%s\n' "# ${ENV_FILE} — создано encar_set_proxy_urls.sh" >"$tmp"
fi
printf '%s\n' "ENCAR_PROXY_URLS=${PROXY_URL}" >>"$tmp"

if getent group "$GROUP" >/dev/null 2>&1; then
  install -m 640 -o root -g "$GROUP" "$tmp" "$ENV_FILE"
else
  install -m 600 -o root -g root "$tmp" "$ENV_FILE"
  echo "Предупреждение: группа ${GROUP} не найдена, файл 600 root:root — поправьте chown/chgrp вручную." >&2
fi
rm -f "$tmp"
echo "OK: ENCAR_PROXY_URLS записан в ${ENV_FILE} (группа ${GROUP})."
