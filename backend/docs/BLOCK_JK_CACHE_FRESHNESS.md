# Блок J+K — свежесть, sold/remove, кэш

## Свежесть (`updated_at`)

- В Postgres у строки каталога есть **`cars.updated_at`** (см. `infrastructure/postgresql/schema.sql`).
- Гидратация **`fetch_cars_by_ids`** / **`fetch_car_any_id`** пробрасывает время в JSON как **`_catalog_updated_at`** (ISO).
- В публичном API:
  - **v1**: опциональное поле **`catalog_updated_at`** на slim-элементе и на **`GET /api/car`** (`result.catalog_updated_at`), если синк с БД есть.
  - **v2** (`WRA_API_CONTRACT_VERSION=v2`): **`catalog_updated_at` обязательно** на slim и detail — контрактные тесты и рантайм-валидация это проверяют.

Сортировки Meilisearch уже используют **`updated_at`** (см. `meilisearch_query.py`).

## Sold / снятие с публикации

- Колонка **`encar_listing_sold`** (и Аналог для Dongchedi) в Postgres; выставляется воркерами (например `encar_listing_live_checker.py`).
- В индекс Meilisearch поле синхронизируется из Postgres (`sync_meilisearch.py`).
- Фильтр листинга по умолчанию исключает проданные: **`build_meilisearch_filter`**.
- В slim/detail флаги **`encar_listing_sold`** / **`dongchedi_listing_sold`** при необходимости пробрасываются в ответ; похожие авто в **`search.py`** отфильтровывают sold при гидратации.

Цель: одно и то же правило «не показывать проданное» на уровне поиска и гидратации.

## Кэш JSON API без «вечно старых» ответов

- Ключи Redis: **`{prefix}:{segment}:{sha256(query)}`** (`fastapi_app/cache.py`).
- Добавлена метка **`WRA_CATALOG_CACHE_EPOCH`** → попадает в query-пары как **`__wra_cache_epoch__`** для сегментов **search**, **similar**, **car**, **facets** (`fastapi_app/cache_epoch.py`). Смена значения (например после массового обновления каталога) даёт **новый ключ** без SCAN.
- По-прежнему доступны: смена **`WRA_REDIS_CACHE_PREFIX`**, **`POST /api/internal/cache/invalidate`** (с секретом), уменьшение TTL в настройках.

## Операционный чеклист

1. После крупного импорта / починки sold: поднять **`WRA_CATALOG_CACHE_EPOCH`** (или инвалидировать кэш).
2. Убедиться, что cron **sync Meilisearch** отрабатывает и индекс содержит актуальный **`updated_at`** / **`encar_listing_sold`**.
3. Для фронта на **v2**: полагаться на **`catalog_updated_at`** для инвалидации локального кэша карточек.
