# Чеклист релиза каталога (API + Meilisearch + кэш)

Использовать перед выкладкой изменений, затрагивающих поиск, индекс, контракт JSON или гидратацию.
**Catalog Pipeline Platform:** после изменений пайплайна — также [`deploy/docs/CATALOG_PIPELINE.md`](../../deploy/docs/CATALOG_PIPELINE.md) и прод-gate ниже.

## 0. Catalog Pipeline (обязательный gate)

- [ ] `deploy/scripts/run_catalog_pipeline_host.sh` (или timer `rideauto-catalog-pipeline`) завершился с кодом 0.
- [ ] Blue/green: `WRA_MEILISEARCH_INDEX=cars_build`, `WRA_MEILI_LIVE_INDEX=cars`, `WRA_MEILI_SWAP_INTO_LIVE=1` (не recreate live in-place).
- [ ] `wra_catalog_meili_documents > 0` и `wra_catalog_index_empty == 0` (textfile / Prometheus).
- [ ] Preflight: `WRA_MEILI_PREFLIGHT_GATE` проходит **или** осознанный override задокументирован в `/etc/default/rideauto` + ops note.
- [ ] Прод: `systemctl list-timers | grep catalog` показывает активный timer.

## 1. Схема и индекс Meilisearch

- [ ] Изменения в `infrastructure/meilisearch/index_settings.json` согласованы с владельцем схемы (`infrastructure/meilisearch/SCHEMA_OWNERS.md`).
- [ ] Прогнан полный или инкрементальный `sync_meilisearch.py` после изменения полей документа / `distinctAttribute`.
- [ ] При смене `filterableAttributes` / `sortableAttributes` — smoke-поиск и фасеты на стейдже.
- [ ] После включения **`catalog_dedupe_key` + `distinctAttribute`**: проверить выдачу и **estimatedTotalHits** / пагинацию на реальных запросах (поведение Meilisearch может отличаться от «сырого» числа документов).

## 2. Postgres

- [ ] Миграции применены (в т.ч. **`008_catalog_dedupe_canonical.sql`**, если используете слияние дублей); `cars.updated_at` / sold-флаги актуальны для гидратации и v2.
- [ ] При массовых правках — мониторинг ночного `postgres_catalog_sync` / catalog pipeline.

## 3. Контракт API

- [ ] `WRA_API_CONTRACT_VERSION`: при bump — golden в `tests/fixtures/api_contract/v*/`, фронт, дока `API_CONTRACT.md`.
- [ ] `pytest` контрактные тесты зелёные.

## 4. Кэш

- [ ] При необходимости сброса: **`WRA_CATALOG_CACHE_EPOCH`** или `POST /api/internal/cache/invalidate`.
- [ ] Edge (Cloudflare): при смене публичного URL API — проверить заголовки кэша для `/api/search`.

## 5. Наблюдаемость

- [ ] `/metrics` доступен scraper’у; после релиза проверить p95 `wra_http_request_duration_seconds` и размеры `wra_http_response_body_bytes` для `/api/search`, `/api/car/{id}`, `/api/facets` (см. `BLOCK_M_SCALE_COST.md`).
- [ ] Textfile: `wra_job_last_*` для `wra_catalog_pipeline` / meili / postgres; lag gauges `wra_catalog_*`.

## 6. Откат

- [ ] Зафиксированы предыдущие значения: версия API, эпоха кэша, UID индекса Meili (при blue/green — пара `index-name` / `live-index-name`).
