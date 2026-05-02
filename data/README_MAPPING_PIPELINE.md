# Цепочка маппинга (Encar / фасеты / мощность)

## Источники правды

| Файл | Назначение |
|------|------------|
| `data/fuel_label_aliases.json` | Единые синонимы топлива KO/RU/EN → канон Ru (API `facet_normalize`, веб `normalizeFuelLabel` после `npm run sync-static-data`) |
| `data/korea_static_terms.json` | Статические EN/RU словари доменов; не затираются ночным скрапером (`build_korea_static_terms.py`) |
| `data/encar_mapping.json` | KO→EN дерево API (марка/модель/…); `engine_hp_resolver` использует блок **mark**; копируется в `web/public/data` |
| `data/engine_map.json` | Оценка л.с.; см. `README_ENGINE_MAP.md` |
| Postgres `term_translation_cache` | Переводы через `PgTermLocalizer` после `bootstrap_korea_term_mapping.py` |

## Типовой порядок (ручной refresh)

1. Снять дерево Encar: `python backend/scripts/encar_fetch_tree.py`
2. Обновить KO→EN: `python backend/scripts/build_encar_mapping.py` → `data/encar_mapping.json`
3. (опц.) `python backend/scripts/build_car_power_lookup.py`
4. При смене топлива: правка **`data/fuel_label_aliases.json`**, затем из каталога **`web`**: `npm run sync-static-data` (копия в `src/lib` + public)
5. Наполнить кэш переводов: `python backend/scripts/bootstrap_korea_term_mapping.py --dsn "$DATABASE_URL"` (в т.ч. **modelGroupName** / `encar_model_group`)

## Docker / Next build

Сборка образа `web` выполняет `npm run build`, который вызывает **sync-static-data**; также `Dockerfile` копирует `data/fuel_label_aliases.json` в `src/lib/`, если sync недоступен к корню монорепо.

## API: дополнить «чистую» KO‑выдачу RU/EN (статика, без Postgres)

`POST /api/catalog/enrich-terms` — JSON с `items`: `[{ "text": "...", "domain": "engine_type"|"fuel"|"modelGroupName"|… }, …]` (до 48 элементов).

- **Строка в ответе** `text_in` — это исходный `trim()`; совпадения по словарям идут по **нормализованному ключу** (NFKC, ideographic space → `\u0020`, схлопывание пробелов), затем при промахе — **без fuzzy по Левенштейну** дополнительная попытка с ключом без пробелов/скобок/тире (`compact_catalog_lookup_variant`).
- **RU** топлива: `fuel_label_aliases.json` + `canon_catalog_fuel_ru`; остальное: `korea_static_terms` / `china_static_terms`, плюс **кросс‑доменный** fallback (generation ↔ configuration ↔ grade и т.д.).
- **EN**: `facet_canonical_english` + при необходимости KO → `romanize`.
- **`use_pg_term_cache: false` (дефолт)** — без чтения Postgres.
- **`use_pg_term_cache: true`** при **`WRA_CATALOG_ENRICH_PG_CACHE_ENABLED=1`** — **read-only** batched `SELECT` по `term_translation_cache` (без `UPDATE hit_count`; до **`WRA_CATALOG_ENRICH_PG_MAX_ROUNDS`** раундов по **`WRA_CATALOG_ENRICH_PG_MAX_KEYS`** ключей за раз). После статики, до LLM. В ответе: **`pg_cache_hits_*`**, **`pg_cache_keys_queried`**, **`pg_truncated`**, **`pg_cache_rounds`**. Таймаут: **`WRA_CATALOG_ENRICH_PG_TIMEOUT_SEC`**. Ошибка/таймаут БД для этого шага — **пропуск** без падения всего метода (частично нули).
- **`use_llm_fallback: false` (дефолт)** — без OpenAI.
- **`use_llm_fallback: true`** — только если на сервере **`WRA_CATALOG_ENRICH_LLM_FALLBACK=1`** и задан ключ **`OPENAI_API_KEY`** или **`WRA_TRANSLATE_API_KEY`**. Порядок: **Redis KV** по паре `{text,domain}` (если настроен `WRA_REDIS_URL`) → LRU в процессе → один batched запрос OpenAI (**лимит** `WRA_CATALOG_ENRICH_LLM_MAX_ITEMS`, по умолчанию 12). В ответе смотреть **`llm_truncated`**, **`llm_still_missing_ru`**, **`llm_openai_http_ok`**; повтор запросом добить хвост.
- **Лимиты и защита**: суммарная длина текстов ограничена **`WRA_CATALOG_ENRICH_MAX_PAYLOAD_CHARS`** (413 если больше). Ограничение частоты: **`WRA_CATALOG_ENRICH_RATE_LIMIT_PER_MINUTE`** (0 = выкл.; при Redis — между воркерами, без Redis — память процесса). По секретному ключу в заголовке лимитируется корзина по хешу ключа иначе по IP клиента.

**Включить/выключить эндпоинт целиком:** **`WRA_CATALOG_ENRICH_ENABLED=1|0`**. Закрыть от посторонних: **`WRA_CATALOG_ENRICH_SECRET`** + **`X-WRA-Catalog-Enrich-Key`**.

### Internal (те же данные без флагов в теле)

`POST /api/internal/catalog/enrich-terms`, тело: **`{ "items": [ ... ] }`**. Авто-PG, если включён **`WRA_CATALOG_ENRICH_PG_CACHE_ENABLED`**. LLM включается **только** если **`WRA_CATALOG_ENRICH_INTERNAL_LLM_FALLBACK=1`** при уже включённом **`WRA_CATALOG_ENRICH_LLM_FALLBACK`** и ключе OpenAI. Авторизация: **`X-WRA-Admin-Key`** = **`WRA_CACHE_INVALIDATE_SECRET`**. Rate-limit публичного enrich сюда **не действует**.

### ETag / дедуп версий

При ответах **без** `use_llm_fallback` клиент может хранить слабый заголовок **`ETag`** (зависит от payload, версии статики **`WRA_CATALOG_ENRICH_ETAG_REVISION`**, **`api_contract_version`**, признака «PG в запросе»). Если включён LLM, **ETag не выставляется** (ответ недетерминирован).

Дополнительно: Prometheus — `wra_catalog_enrich_llm_calls_total`, `wra_catalog_enrich_llm_http_seconds`, сегменты **`catalog_enrich_pair_redis`** и **`catalog_enrich_pg_batch`** в `wra_cache_lookups_total`; пути `/api/catalog/enrich-terms` и `/api/internal/catalog/enrich-terms` группируются в метриках.

## CI

- `backend`: `python -m json.tool data/fuel_label_aliases.json`; полный pytest.
- `next-build`: синтаксис JSON, `node scripts/sync-static-data.mjs`, затем **`python backend/scripts/ci_verify_fuel_alias_sync.py`** и `npm run build`.
