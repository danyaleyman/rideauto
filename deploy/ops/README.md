# deploy/ops — удалённые операции без секретов в коде

Параметризованная замена десятков одноразовых `deploy/scripts/_remote_*.py`, в которых
были захардкожены IP сервера, логин `root`, пароль (через argv) и даже мастер-ключ
Meilisearch. Здесь подключение и секреты берутся **только** из окружения или
gitignored-файла `deploy/.env.deploy`.

## Установка

```bash
pip install -r deploy/requirements-deploy.txt   # paramiko
cp deploy/.env.deploy.example deploy/.env.deploy # заполнить host/ключ
```

Рекомендуется ключ (`RIDEAUTO_DEPLOY_SSH_KEY`), а не пароль.

## Команды

```bash
python -m deploy.ops status              # docker compose ps + /api/health
python -m deploy.ops health              # deep health, exit 1 при ошибке

python -m deploy.ops migrate status      # раннер миграций внутри api
python -m deploy.ops migrate apply
python -m deploy.ops migrate check

python -m deploy.ops meili-sync                  # секреты из env контейнера
python -m deploy.ops meili-sync --preflight-gate

python -m deploy.ops rebuild-web         # build + up web
python -m deploy.ops deploy              # git pull + rebuild web + migrate apply/check
python -m deploy.ops deploy --skip-migrate

После выката B2C (push + `/admin/leads`):

```bash
python -m deploy.ops migrate apply       # в т.ч. 015_push_subscriptions.sql
# В /etc/default/rideauto: WRA_PUSH_VAPID_* , WRA_LISTING_ADMIN_EMAILS , WRA_AUTH_*
python -m deploy.ops rebuild-web         # generate:seo-landings в npm run build
```

python -m deploy.ops tail /tmp/che168-ym-backfill.log -n 50
python -m deploy.ops upload ./local.tar.gz /tmp/local.tar.gz

# Произвольные операции (без написания нового скрипта):
python -m deploy.ops run -- "docker compose logs --tail 50 api"
python -m deploy.ops compose -- logs --tail 100 web
python -m deploy.ops api-exec -- "python -c 'import sys;print(sys.version)'"
python -m deploy.ops psql -- "SELECT count(*) FROM cars WHERE source='che168'"
```

`run` / `compose` / `api-exec` / `psql` покрывают разовые диагностики, ради которых
раньше плодились `_remote_*.py`. Если операция повторяется — добавьте подкоманду в
`deploy/ops/cli.py` и билдер в `deploy/ops/commands.py` (билдеры — чистые и покрыты тестами).

## Безопасность

- Ни хоста, ни логина, ни паролей/ключей в репозитории.
- `deploy/.env.deploy` в `.gitignore`.
- `meili-sync` подставляет `WRA_MEILISEARCH_KEY/URL` и `WRA_PG_DSN` из окружения
  контейнера `api` в рантайме — секреты не проходят через наш код.
- Старые `deploy/scripts/_remote_*.py` и корневые `tmp_*.json` добавлены в `.gitignore`,
  чтобы утёкшие секреты не попали в историю. Локально их можно удалить — логика
  перенесена сюда.

Одноразовая локальная зачистка устаревших ad-hoc скриптов (НЕ обязательна, PowerShell):

```powershell
Get-ChildItem deploy/scripts/_remote_*.py | Remove-Item
```
