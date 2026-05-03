# Блок I — канон фасетов, анти-мусор, drift

## Канон

| Артефакт | Назначение |
|----------|------------|
| `fastapi_app/meilisearch_query.FACET_SPECS_MEILI` | Публичный ключ ответа → множество имён в query → атрибут Meilisearch |
| `fastapi_app/facet_normalize.FACET_MEILI_ATTR_TO_EN_DOMAIN` | Атрибут Meili → домен `facet_canonical_english` (China cleanup в `_cleanup_china_facet_value`) |
| `localization/term_localizer.facet_canonical_english` | Статическая EN/транслит-канонизация для марок, моделей, поколений, комплектаций |
| `fastapi_app/schemas/api.FacetsResponse` | Порядок полей в JSON **должен** совпадать с публичными ключами из `FACET_SPECS_MEILI` (см. drift-тесты) |

## Анти-мусор (частично)

- **Korea / transmission**: строки, похожие на чистые числа (`_JUNK_TRANS_NUMERIC`), отфильтровываются в `merge_facet_distribution_rows` перед группировкой.
- **Korea / fuel, color, body**: слияние синонимов и скрытие неразмеченных KO-подписей (см. `tests/test_facet_expand_synonyms.py`).
- **China**: нормализация подписей через `_cleanup_china_facet_value` и группировка по нижнему регистру без потери сырья в bucket.

## Drift-тесты

`tests/test_facet_specs_drift.py` фиксирует:

- число измерений и тройки `(public_key, url_omit, meili_attr)`;
- согласованность `FACET_MEILI_ATTR_TO_EN_DOMAIN` с атрибутами из спецификации;
- стабильность ключей `meilisearch_sort_list`;
- выравнивание `FacetsResponse` с `FACET_SPECS_MEILI`.

При добавлении фасета: обновить **все** места выше и golden/доки при необходимости.
