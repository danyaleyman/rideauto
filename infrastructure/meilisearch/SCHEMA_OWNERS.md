# Владение схемой индекса Meilisearch (`cars`)

## Зона ответственности

| Область | Файлы / артефакты | Владелец (заполнить) |
|---------|-------------------|----------------------|
| Документ синка | `infrastructure/meilisearch/sync_meilisearch.py`, `backend/catalog_dedupe.py`, миграция `008_catalog_dedupe_canonical.sql`, `backend/scripts/catalog_dedupe_link.py` | _команда каталога / @…_ |
| Настройки индекса | `infrastructure/meilisearch/index_settings.json` | _тот же_ |
| Фильтры и сортировки API | `backend/fastapi_app/meilisearch_query.py` | _тот же_ |
| Фасеты UI ↔ API | `backend/fastapi_app/facet_normalize.py`, drift `tests/test_facet_specs_drift.py` | _тот же_ |

## Правила PR

1. Любое изменение **`index_settings.json`** или полей документа в `row_to_document` — **явное упоминание** в описании PR и обновление drift/контрактных тестов при необходимости.
2. Слияние без прогона синка на стейдже не допускается для изменений, влияющих на фильтруемые атрибуты.
3. При спорных изменениях ранжирования — зафиксировать решение в `backend/docs/BLOCK_I_FACET_CANON.md` или отдельной ADR.

## GitHub CODEOWNERS (рекомендация)

Добавьте в корневой `.github/CODEOWNERS` строки вида:

```gitattributes
/infrastructure/meilisearch/ @your-org/catalog-team
/backend/fastapi_app/meilisearch_query.py @your-org/catalog-team
```

(Подставьте реальные команды — в репозитории файл не создан намеренно.)
