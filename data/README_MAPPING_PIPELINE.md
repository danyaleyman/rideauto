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

## API: дополнить «чистую» KO‑выдачу RU/EN (без LLM)

`POST /api/catalog/enrich-terms` — батч из пар `{ "text": "...", "domain": "engine_type"|"fuel"|"modelGroupName"|… }`.

- **RU** топлива по `fuel_label_aliases.json` + логика фасетов (`canon_catalog_fuel_ru`); для остальных доменов — `korea_static_terms` / `china_static_terms` (`ru`).
- **EN** — `facet_canonical_english` + при необходимости латиница KO (`romanize`).
- Выключить: **`WRA_CATALOG_ENRICH_ENABLED=0`**. Закрыть от посторонних: **`WRA_CATALOG_ENRICH_SECRET`** + заголовок **`X-WRA-Catalog-Enrich-Key`** с тем же значением.

Полное покрытие как у ночного `postgres_catalog_sync` здесь недостижимо (нет БД‑кэша переводов) — можно позже добавить ветку с `PgTermLocalizer`.

## CI

- `backend`: `python -m json.tool data/fuel_label_aliases.json`; полный pytest.
- `next-build`: синтаксис JSON, `node scripts/sync-static-data.mjs`, затем **`python backend/scripts/ci_verify_fuel_alias_sync.py`** и `npm run build`.
