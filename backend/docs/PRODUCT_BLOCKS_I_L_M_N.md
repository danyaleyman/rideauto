# Дорожная карта блоков I, L, M, N

Краткие контуры следующих эпиков после F+G и J+K. Детали по мере реализации — отдельные BLOCK\_\*.md или задачи в трекере.

## I — Канон фасетов, анти-мусор, drift

Подробно: **`docs/BLOCK_I_FACET_CANON.md`**.

- **Канон**: единый проход нормализации значений (см. `facet_normalize.py`, `term_localizer.py`, `FACET_SPECS_MEILI`, `FACET_MEILI_ATTR_TO_EN_DOMAIN`).
- **Анти-мусор**: пороги частоты, чёрные списки опечаток, слияние синонимов перед попаданием в индекс (частично уже в `merge_facet_distribution_rows` / expand).
- **Drift-тесты**: `tests/test_facet_specs_drift.py` (измерения, атрибуты Meili, URL-omit, сортировки, согласованность с `FacetsResponse`). Дальше — снапшоты распределений или контракт «допустимые префиксы значений» по доменам.

## L — Дедуп

Подробно: **`docs/BLOCK_L_DEDUP.md`**.

- **Meilisearch**: поле `catalog_dedupe_key` и `distinctAttribute` в `index_settings.json` (схлопывание хитов в поиске).
- **Фронт**: `catalog-vin-dedupe` остаётся подстраховкой.
- **Postgres**: опционально — каноническая строка и слияние дублей (следующий шаг зрелости).

## M — Масштаб и стоимость

Подробно: **`docs/BLOCK_M_SCALE_COST.md`**.

- Профилирование горячих путей: поиск, гидратация, enrich, sync.
- Бюджеты: размер ответа (slim + `read_model`), частота sync, TTL кэша, размер индекса Meilisearch.

## N — Governance

Подробно: **`docs/BLOCK_N_GOVERNANCE.md`**.

- Версионирование API (`WRA_API_CONTRACT_VERSION`, golden v1/v2).
- Runbook: кто меняет `WRA_CATALOG_CACHE_EPOCH`, как катить v2, как откатывать clean-read (см. `BLOCK_D_CLEAN_ROLLOUT.md`).
- Аудит изменений схемы индекса Meilisearch и миграций Postgres.

## Аудит зрелости (J+K, I, L, M, N)

Сводная оценка и пробелы: **`docs/AUDIT_CATALOG_MATURITY_JK_I_LMN.md`**.
