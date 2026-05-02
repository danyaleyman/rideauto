# Контур ценообразования и `pricing_clean`

## Контракт (единый материализатор)

1. **Источник истины по рублёвой цене и tier для каталога** — результат работы **`postgres_catalog_sync.py` с расчётом цен** (без `--no-prices`). Он обновляет `cars.data` (включая `my_price`, `pricing_tier`, `pricing_clean`) и колонку `cars.price_rub`.
2. Любой код, который **меняет `cars.data`** в обход этого синка (парсер только до очереди, воркер intent, backfill л.с., reprocess raw), обязан выставить **`needs_pricing_recompute = true`** на строке `cars`, чтобы следующий полный синк с ценами **догнал** tier и рубли.
3. **Ингест** (Encar saver, Dongchedi batch upsert) выставляет флаг через UPSERT: `needs_pricing_recompute` становится true; после прогона синка **с ценами** флаг **сбрасывается** автоматически.

## Очередь `needs_pricing_recompute`

- Колонка: `cars.needs_pricing_recompute` (миграция `007_pricing_recompute_queue.sql`). UPSERT каталога также ожидает колонку `encar_model_group` (`006_encar_model_group_column.sql`); без неё `postgres_catalog_sync` завершится ошибкой.
- **Сброс в false**: при UPSERT из `postgres_catalog_sync`, если синк запущен **без** `--no-prices` (пересчитали цены для выгружаемого набора листингов).
- **Сохранение / довыставление true**: при `--no-prices` колонка обновляется как `(старая OR новая из upsert)` — очередь не теряется.
- Индекс: `idx_cars_needs_pricing_recompute_encar` (Encar, флаг true).

## Версия правил

- В `pricing_clean` пишется **`pricing_rules_version`** (константа `PRICING_RULES_VERSION` в `catalog_encar_pricing.py`).
- При изменении правил tier или калькулятора **увеличьте константу** и прогоните синк с ценами; при необходимости — `repair_encar_pricing_recompute_queue.py` для постановки в очередь по несовпадению версии.

## Рекомендуемый порядок в проде

1. Ingest / `encar_daily_update` (новые и обновлённые карточки).
2. Воркеры (intent, sold-checker и т.д.) — только правки `data` + **`needs_pricing_recompute`** где нужно.
3. **`postgres_catalog_sync` с ценами** и Meilisearch (см. `deploy/scripts/run_postgres_catalog_sync_host.sh`).
4. Периодически (например, раз в сутки): **`repair_encar_pricing_recompute_queue.py --apply`** или мониторинг метрик из stderr синка.

## Наблюдаемость

В конце успешного upsert-блока `postgres_catalog_sync` в stderr печатается строка вида:

`Pricing observability: needs_pricing_recompute=N encar_rows_old_pricing_rules_version≈M (current=…)`.

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `backend/postgres_catalog_sync.py` | Материализация цен, сброс очереди при прогоне с ценами |
| `backend/scripts/repair_encar_pricing_recompute_queue.py` | Пометить «устаревшие» Encar JSON на пересчёт (с хоста подставляет `postgres` → `127.0.0.1` в DSN, как `deploy/scripts/pg_dsn_host_local_rewrite.py`) |

Обновления **`cars.data`** (или существенных полей для прайсинга) делают **`needs_pricing_recompute = TRUE`** в: saver/upsert, `encar_price_intent_live_worker`, `backfill_cars_power_from_hp_catalog`, `reprocess_from_raw_envelope`, `backfill_china_canonical_names`, `postgresql_database` (legacy upsert при смене `data`). Чекеры **sold** (`encar_listing_live_checker`, `dongchedi_listing_live_checker`) трогают только флаги листинга — очередь не требуется.

## Read-path

`read_models.build_catalog_read_model` может **временно** согласовать tier с живыми полями карточки; окончательное состояние БД и рубль после `clear_estimated_price_fields` всё равно даёт **синк с ценами**.

## Пустой каталог на сайте после синка

Каталог в UI обычно идёт из **Meilisearch**. Если включён **`WRA_MEILI_PREFLIGHT_GATE`** и в БД мало строк с `price_rub` (порог по умолчанию ~97% для Encar), `sync_meilisearch.py` завершается с **кодом 2** и **не добавляет документы**. После сброса volume Meili или `--recreate-index` индекс может оказаться пустым, а повторный синк его не заполняет, пока preflight не пройдёт.

**Что сделать:** на время наполнения выставить `WRA_MEILI_PREFLIGHT_GATE=false` (в `.env` или только на команду синка) и снова запустить `postgres_catalog_sync` / `sync_meilisearch.py`; либо вручную вызвать `sync_meilisearch.py` с меньшим `--preflight-min-price-coverage-pct`. Долгосрочно — поднять долю карточек с ценой в Postgres или ослабить пороги осознанно.
