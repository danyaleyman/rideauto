# Резервное копирование и восстановление (RideAuto)

## PostgreSQL

**Логический дамп (рекомендуется для восстановления в том же major Postgres):**

```bash
pg_dump "$DATABASE_URL" --format=custom --file=rideauto_catalog_$(date -u +%Y%m%d).dump
```

**Восстановление в пустую БД:**

```bash
pg_restore --clean --if-exists --dbname="$DATABASE_URL" rideauto_catalog_YYYYMMDD.dump
```

**Только схема (без данных):**

```bash
pg_dump "$DATABASE_URL" --schema-only -f schema.sql
```

Храните дампы вне сервера приложения; проверяйте периодическое тестовое восстановление на стейдж.

## Meilisearch

- Данные индекса **не** являются источником истины — восстановление: **полный re-sync** из Postgres (`infrastructure/meilisearch/sync_meilisearch.py` или пайплайн `postgres_catalog_sync`).
- При необходимости снимайте снапшот тома с `meili_data` в Docker / k8s PV (зависит от инсталляции).
- После восстановления Postgres всегда **переиндексируйте** Meilisearch и примените `index_settings.json`.

## Redis

- Кэш JSON API и enrich KV **допустимо потерять** — восстановление не критично; при необходимости очистите ключи или смените `WRA_REDIS_CACHE_PREFIX` / `WRA_CATALOG_CACHE_EPOCH`.

## Секреты и env

- Дублируйте `.env` / секрет-менеджер оффлайн согласно политике команды.

## RPO / RTO

- Задайте целевые **RPO/RTO** для каталога (частота дампов, SLA восстановления) и зафиксируйте в runbook команды.
