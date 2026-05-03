# Публичный контракт API каталога (блок F+G)

Версия контракта задаётся **`WRA_API_CONTRACT_VERSION`** (по умолчанию `v1`) и пробрасывается в ответы как `meta.api_version`, `api_version` у карточки, `api_contract_version` у slim-элемента, а также в `read_model_version` детальной карточки (`car_detail.{version}`).

При смене несовместимой формы ответа **поднимите** `WRA_API_CONTRACT_VERSION` (например `v2`), обновите фронт; golden лежат в `tests/fixtures/api_contract/v1|v2/`, контроль версий — **`SUPPORTED_API_CONTRACT_FIXTURE_VERSIONS`**.

### v1 vs v2

| | **v1** (по умолчанию) | **v2** |
|--|------------------------|--------|
| **`catalog_updated_at`** | Опционально (если в БД есть `updated_at`) | **Обязательно** на каждом slim-элементе и в `GET /api/car` → `result.catalog_updated_at` |
| **`read_model_version`** | `car_detail.v1` | `car_detail.v2` |
| **Фронт** | Может игнорировать timestamp | Должен использовать **`catalog_updated_at`** для свежести кэша |

Инвалидация JSON-кэша без SCAN: **`WRA_CATALOG_CACHE_EPOCH`** (см. **`BLOCK_JK_CACHE_FRESHNESS.md`**).

## Pydantic и проверка в рантайме

| Модуль | Назначение |
|--------|------------|
| `fastapi_app/schemas/catalog_contract.py` | **`SlimCatalogItemV1`** — shape slim-элемента (включая вложенный **`read_model`**); **`CatalogReadModelV1`**; **`CarDetailEnvelopeV1`**. |
| `validate_slim_catalog_item_v1` | Конец **`slim_catalog_car`**; при **v2** требует **`catalog_updated_at`**. |
| `validate_catalog_search_response_v1` | После **`SearchResponse.model_dump()`** в кэшируемом compute поиска: проверка `meta` + в slim-режиме каждого элемента. |
| `validate_catalog_similar_response_v1` | То же для **`/api/similar`** (всегда slim). |
| `validate_car_detail_envelope_v1` | После сборки **`GET /api/car/{car_ref}`**. |

Обязательные ключи slim: **`SLIM_ITEM_V1_REQUIRED_KEYS`**.

## GET `/api/search`, `/api/cars`

Тело после кэша соответствует **`SearchResponse`** (`fastapi_app/schemas/api.py`):

| Поле | Тип | Описание |
|------|-----|----------|
| `result` | `array` | При **`meta.list_mode=slim`** — элементы **`SlimCatalogItemV1`**. При **`full=1`** — сырой объект строки Postgres (проверяется только как `object[]`, без slim-формы). |
| `meta` | `object` | Проверяется схемой **`SearchCatalogMetaV1`** (см. `catalog_contract.py`). |

Параметр запроса **`full`** задокументирован в OpenAPI (`1` = режим отладки / внутренние сценарии).

### Элемент `result[]` в режиме slim (`list_mode=slim`)

Формируется **`slim_catalog_car`**.

**Обязательные ключи верхнего уровня:**

| Ключ | Тип | Источник |
|------|-----|----------|
| `id` | `string` | `car_id` |
| `title` | `string` | EN / канон / сырой текст из `data` |
| `data` | `object` | Подмножество из `cars.data` по **`_SLIM_CATALOG_DATA_KEYS`** |
| **`read_model`** | `object` | Тот же **`build_catalog_read_model`**, что и на карточке (цена, tier, спека, л.с.) — **без второго запроса** для типового UI списка |
| `price` | `number \| null` | Развёрнуто из read model / fallback `my_price` |
| `price_on_request` | `boolean` | Read model + эвристики |
| `year_num` | `integer` | Из `data.year` |
| `api_contract_version` | `string` | Копия `WRA_API_CONTRACT_VERSION` |

**Частые опциональные ключи:** `inner_id`, `pricing_tier`, `customs_included`, `catalog_created_at`, `encar_listing_reserved`, `encar_listing_sold`, `dongchedi_listing_sold`.

Для отображения спеки в списке предпочтительно **`read_model`**, дубли в **`data`** — см. **`API_DEPRECATIONS.md`**.

## GET `/api/similar`

**`SimilarResponse`**: `result` типизирован как **`list[SlimCatalogItemV1]`** в OpenAPI; ответ проходит **`validate_catalog_similar_response_v1`**.

## GET `/api/car/{car_ref}`

**`CarDetailResponse`**: `api_version` + **`result`**.

### Объект `result` (нормализованный вид)

**`build_car_detail_read_model`** всегда возвращает:

- **`id`** — строка;
- **`data`** — объект карточки: либо копия вложенного `row.data`, либо при **плоском** JSON в БД — все поля строки, кроме служебных (`id`, `_catalog_created_at`, флаги продажи и т.д.), без «размазанных» дублей марки/модели на корне;
- **`read_model`**, **`read_model_version`**;
- при наличии: **`_catalog_created_at`**, **`encar_listing_sold`**, **`dongchedi_listing_sold`**.

### Поля **`read_model`**

Семантика как в dual-run: clean-слои при rollout, **`power_hp`**: `integer | null`.

## Golden-тесты и smoke

- `backend/tests/fixtures/api_contract/v1/` — эталонные JSON.
- `backend/tests/test_api_contract_snapshots.py`, `test_api_contract_car_route.py`.
- `backend/tests/test_asgi_smoke.py` — **`TestClient` + lifespan**, пул Postgres замокан (проверка `/api/health`).

## Устаревшие поля

См. **`API_DEPRECATIONS.md`**.
