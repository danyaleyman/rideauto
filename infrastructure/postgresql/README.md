# PostgreSQL: схема и миграции

## Файлы

- `schema.sql` — базовая схема (загружается init-скриптом контейнера `postgres` при
  первом старте: `docker-entrypoint-initdb.d`). Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
- `migrations/NNN_*.sql` — инкрементальные миграции. Применяются **поверх** `schema.sql`.
  Все идемпотентны (`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, …).
- `migrate.py` — раннер: отслеживает применённые миграции в таблице `schema_migrations`,
  детектит дрейф (изменение уже применённого файла) и недостающие файлы.

## Правила

1. **Имя файла:** `NNN_slug.sql` (3+ цифр, затем `lowercase_slug`). Номер уникален и растёт.
2. **Применённая миграция неизменяема.** Не редактируйте уже накатанный файл — раннер
   засечёт несовпадение контрольной суммы (`check` вернёт ошибку). Нужны правки → новый файл.
3. **Идемпотентность.** Пишите так, чтобы повторное применение не падало
   (`IF NOT EXISTS` / `IF EXISTS`).

## Использование

DSN берётся из (по приоритету): `--dsn`, `$MIGRATE_DSN`, `$WRA_PG_DSN`, `$DATABASE_URL`.

```bash
# Статус (read-only): какие применены, какие ожидают
python infrastructure/postgresql/migrate.py status

# Применить все ожидающие
python infrastructure/postgresql/migrate.py apply

# CI-гейт: exit 1, если есть pending или дрейф
python infrastructure/postgresql/migrate.py check
```

### Внутри docker compose

```bash
docker compose exec api python /app/infrastructure/postgresql/migrate.py status
docker compose exec api python /app/infrastructure/postgresql/migrate.py apply
```

(каталог `infrastructure/postgresql` смонтирован в `api` как read-only volume.)

### На VPS (хост, БД на 127.0.0.1)

```bash
MIGRATE_DSN="postgresql://wra:***@127.0.0.1:5432/wra" \
  python infrastructure/postgresql/migrate.py apply
```

## Адаптация на существующей БД (baseline)

Если схема уже накатывалась вручную до появления раннера, пометьте текущие файлы
применёнными **без выполнения SQL**, чтобы `apply` не пытался накатить их повторно:

```bash
python infrastructure/postgresql/migrate.py baseline           # все файлы
python infrastructure/postgresql/migrate.py baseline --upto 11 # только до 011 включительно
```

Поскольку все миграции идемпотентны, `apply` на существующей БД тоже безопасен — `baseline`
нужен лишь чтобы привести таблицу `schema_migrations` в актуальное состояние.

## CI

Джоба `db-migrations` (`.github/workflows/ci.yml`) на чистом Postgres:
загружает `schema.sql` → `apply` → повторный `apply` (no-op) → `check`. Падает,
если миграция не накатывается, нарушена идемпотентность или появился дрейф.
