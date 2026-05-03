# Блок L — дедупликация

## Ключ `catalog_dedupe_key` (бэкенд + индекс)

- Модуль **`backend/catalog_dedupe.py`**: нормализация VIN (как на фронте, длина ≥ 11 после очистки), иначе `source:inner_id`, иначе `id:car_id`.
- **Meilisearch**: поле **`catalog_dedupe_key`** пишется в `infrastructure/meilisearch/sync_meilisearch.py` (`row_to_document`).
- **`index_settings.json`**: атрибут **filterable** и **`distinctAttribute": "catalog_dedupe_key"`** — в выдаче поиска не более одного документа на ключ (релевантность по правилам ранжирования Meilisearch).
- После изменения настроек нужен **полный прогон settings + реиндекса** (или `--settings-only` + инкрементальный sync документов с новым полем).

### Ограничения

- **`estimatedTotalHits` и пагинация** при `distinct` могут вести себя иначе, чем без дедупа — проверять на стейдже (см. `RELEASE_CHECKLIST_CATALOG.md`).
- Документы без поля (старый индекс) не дедупятся, пока не переиндексированы.

## Фронт

- **`web/src/lib/catalog-vin-dedupe.ts`** — дополнительная склейка по VIN в UI; приоритет **`catalog_updated_at`**, иначе **`catalog_created_at`**. Имеет смысл оставить как подстраховку и для мгновенной консистентности до полного синка.

## Postgres — ручное слияние дублей

- Миграция **`008_catalog_dedupe_canonical.sql`**: колонка `dedupe_canonical_car_id`.
- Скрипт **`backend/scripts/catalog_dedupe_link.py`**: связать дубликат с каноническим `car_id`; дубликат перестаёт попадать в выборку синка Meili; API отдаёт данные канонической строки.
- Скрипт **`backend/scripts/catalog_dedupe_suggest.py`**: потоковый отчёт по строкам без `dedupe_canonical_car_id`, группировка по тому же `catalog_dedupe_key`, что и индекс (dry-run; дальше — ручной `catalog_dedupe_link`).

## Postgres (дальнейшая зрелость)

- Фоновый job, помечающий дубли по эвристике, и политика «одна активная строка на VIN» без ручного CLI — по мере роста каталога.
