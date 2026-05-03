# Чеклист релиза каталога (API + Meilisearch + кэш)

Использовать перед выкладкой изменений, затрагивающих поиск, индекс, контракт JSON или гидратацию.

## 1. Схема и индекс Meilisearch

- [ ] Изменения в `infrastructure/meilisearch/index_settings.json` согласованы с владельцем схемы (`infrastructure/meilisearch/SCHEMA_OWNERS.md`).
- [ ] Прогнан полный или инкрементальный `sync_meilisearch.py` после изменения полей документа / `distinctAttribute`.
- [ ] При смене `filterableAttributes` / `sortableAttributes` — smoke-поиск и фасеты на стейдже.
- [ ] После включения **`catalog_dedupe_key` + `distinctAttribute`**: проверить выдачу и **estimatedTotalHits** / пагинацию на реальных запросах (поведение Meilisearch может отличаться от «сырого» числа документов).

## 2. Postgres

- [ ] Миграции применены (в т.ч. **`008_catalog_dedupe_canonical.sql`**, если используете слияние дублей); `cars.updated_at` / sold-флаги актуальны для гидратации и v2.
- [ ] При массовых правках — мониторинг ночного `postgres_catalog_sync`.

## 3. Контракт API

- [ ] `WRA_API_CONTRACT_VERSION`: при bump — golden в `tests/fixtures/api_contract/v*/`, фронт, дока `API_CONTRACT.md`.
- [ ] `pytest` контрактные тесты зелёные.

## 4. Кэш

- [ ] При необходимости сброса: **`WRA_CATALOG_CACHE_EPOCH`** или `POST /api/internal/cache/invalidate`.
- [ ] Edge (Cloudflare): при смене публичного URL API — проверить заголовки кэша для `/api/search`.

## 5. Наблюдаемость

- [ ] `/metrics` доступен scraper’у; после релиза проверить p95 `wra_http_request_duration_seconds` и размеры `wra_http_response_body_bytes` для `/api/search`, `/api/car/{id}`, `/api/facets` (см. `BLOCK_M_SCALE_COST.md`).

## 6. Откат

- [ ] Зафиксированы предыдущие значения: версия API, эпоха кэша, UID индекса Meili (при blue/green — пара `index-name` / `live-index-name`).
