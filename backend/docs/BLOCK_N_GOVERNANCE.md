# Блок N — governance

## Версия публичного API

- `WRA_API_CONTRACT_VERSION` (`v1` / `v2`): golden в `tests/fixtures/api_contract/{v1,v2}/`, список версий в `SUPPORTED_API_CONTRACT_FIXTURE_VERSIONS`.
- **v2**: обязательный `catalog_updated_at` на slim и detail; см. `docs/API_CONTRACT.md`.

## Кэш и инвалидация

- **`WRA_CATALOG_CACHE_EPOCH`**: смена значения пересобирает ключи Redis без SCAN (см. `docs/BLOCK_JK_CACHE_FRESHNESS.md`).
- **`POST /api/internal/cache/invalidate`**: по секрету `X-WRA-Admin-Key` / `cache_invalidate_secret`.
- **`WRA_REDIS_CACHE_PREFIX`**: жёсткая смена пространства ключей.

## Clean read

- Процент и режим: `WRA_CLEAN_READ_MODE`, `WRA_CLEAN_READ_PERCENT` — см. `docs/BLOCK_D_CLEAN_ROLLOUT.md`.
- Тесты изолируют `WRA_CLEAN_READ_PERCENT` через `tests/conftest.py`, чтобы хостовый env не ломал CI.

## Индекс Meilisearch и Postgres

- Изменение фильтруемых/сортируемых полей в индексе — версионировать в PR, обновить drift-тесты фасетов и доку миграций.
- Миграции SQL — только через принятую в репозитории схему (`infrastructure/postgresql/`).
- **Владелец схемы индекса** и правила PR: `infrastructure/meilisearch/SCHEMA_OWNERS.md`.
- **Чеклист релиза каталога**: `backend/docs/RELEASE_CHECKLIST_CATALOG.md`.
- **ADR** для спорных изменений индекса: `docs/adr/` (см. `docs/adr/README.md`).
- **CODEOWNERS**: шаблон `.github/CODEOWNERS` — раскомментируйте команды после настройки org.

## Runbook (кратко)

1. Катить **v2**: поднять версию на бэкенде и фронте, проверить наличие `updated_at` в гидратации, прогнать контрактные тесты.
2. Массовое обновление каталога: поднять **`WRA_CATALOG_CACHE_EPOCH`** или вызвать инвалидацию кэша.
3. Откат: вернуть `WRA_API_CONTRACT_VERSION=v1`, предыдущую эпоху кэша при необходимости.
