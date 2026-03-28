# Каталог двигателей `engine_map.json`

Используется модулем `backend/engine_hp_resolver.py` для оценки мощности (л.с.), когда Encar не отдаёт `power`.

## Порядок обогащения

1. Парсер (`parser_full.py`): Encar → `car_power_lookup.json` → разбор строки (마력/hp) → **engine_map**.
2. Экспорт (`export_from_scraper_db.py`): если `power` пусто → `get_power_for_car()` → **engine_map** → `power_lookup.json`.

При совпадении с каталогом в данные пишутся `power_source: "engine_map"` и `power_estimated: true` (на сайте показывается **≈**).

## Формат записи

| Поле | Описание |
|------|-----------|
| `make` | Марка латиницей (как после маппинга из `encar_mapping.json`, например `Hyundai`, `BMW`) |
| `make_ko` | Опционально корейское имя марки для матча (`현대`, `기아`) |
| `model_substrings` | Список подстрок; хотя бы одна должна входить в склеенные поля модели/комплектации (регистр не важен) |
| `cc` | Точный объём, см³ |
| `cc_min` / `cc_max` | Диапазон объёма |
| `turbo` | `true` / `false`; если поля нет — не фильтруем по турбо |
| `fuel` | `gas`, `diesel`, `hybrid`, `electric`, `lpg` или пропуск |
| `hp` | Мощность, л.с. |
| `year_min` / `year_max` | Опционально ограничение по году |
| `priority` | Чем выше, тем предпочтительнее при нескольких совпадениях |
| `match_all_models` | Только если **нет** `model_substrings`: `true` = любая модель этой марки (осторожно) |
| `motor_codes` / `engine_codes` | Коды из инспекции Encar (`motorType`, напр. `B48A20E`, `D4HB`). Если заданы — матч по коду (точно или префикс ≥4 симв.); `model_substrings` тогда опциональны (если пусто — достаточно кода + марки + объёма) |

Турбо эвристически определяется по grade/model: `T-GDI`, `1.6T`, `터보`, `CRDi`, `JCW`, `Cooper S` и т.д.

## Автообучение

Скрипт **`backend/scripts/auto_learn_engine_map.py`** сам находит данные:

1. `frontend/cars.json`, иначе  
2. `frontend/data/chunks/cars_*.json`, иначе  
3. `encar_cars.db`

Берёт только объявления с **реальной** мощностью (не `power_source=engine_map`), с **`motorType`** в отчёте и с **объёмом**. Группирует по марке + коду мотора + см³ + топливо + турбо; если в группе ≥3 машин и разброс л.с. небольшой — добавляет строку с `auto_learned: true`.

```bash
python backend/scripts/auto_learn_engine_map.py
python backend/scripts/auto_learn_engine_map.py --dry-run
```

После экспорта в JSON (опционально):

```bash
python backend/export_from_scraper_db.py ... --learn-engine-map
# или переменная окружения:
set AUTO_LEARN_ENGINE_MAP=1
```

## Точность

Это **оценка по типовым моторным рядам**, не замена данным с завода. Для редких версий добавляйте отдельные строки с узким `cc_*`, `year_*` и маркерами в `model_substrings` (например `330i`, `N Line`).

## Расширение

1. Смотрите в выгрузке пустой `power` при известном `displacement` и типичной модели.
2. Добавьте строку в `engines`, проверьте:  
   `python -c "import sys; sys.path.insert(0,'backend'); from engine_hp_resolver import resolve_engine_hp; print(resolve_engine_hp({...}))"`
