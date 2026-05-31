# PostgreSQL: бэкап и восстановление

## Автоматический бэкап (рекомендуется)

1. Скопируйте unit-файлы на сервер:

```bash
sudo cp deploy/systemd/rideauto-pg-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rideauto-pg-backup.timer
systemctl list-timers | grep rideauto-pg-backup
```

2. Ручной прогон:

```bash
cd /opt/rideauto
bash deploy/scripts/backup_pg.sh
```

Дампы: `backups/wra_YYYYMMDD_HHMMSS.dump`, симлинк `backups/wra_latest.dump`.  
Ротация: `BACKUP_RETENTION_DAYS` (по умолчанию 14).

### Облако (Yandex Disk / Mail.ru / S3)

```bash
# один раз
rclone config   # remote name: yandex

# в /opt/rideauto/.env
RCLONE_REMOTE=yandex:rideauto-backups
```

## Restore drill (не трогает prod БД `wra`)

```bash
bash deploy/scripts/restore_pg_drill.sh backups/wra_latest.dump
```

Создаётся БД `wra_restore_test`, туда `pg_restore`, затем `migrate.py check`.

## Мониторинг

- `GET /api/health?deep=1` — PG, Redis, Meilisearch + coverage ratio
- Cron: `deploy/scripts/health_watchdog.sh` (exit 1 → алерт)
- Prometheus: `wra_health_meili_coverage_ratio`, алерты в `deploy/monitoring/alert_rules.yml`

## Откат миграции (downgrade)

Только для миграций с файлом `{version}.down.sql` (сейчас: `008_catalog_dedupe_canonical`).

```bash
python infrastructure/postgresql/migrate.py rollback --version 008_catalog_dedupe_canonical
python infrastructure/postgresql/migrate.py apply
```

CI прогоняет rollback/re-apply на чистом Postgres.
