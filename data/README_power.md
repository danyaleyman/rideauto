# Мощность (л.с.) из внешних источников

## Как заполняется мощность

1. **NHTSA (США)** — по VIN номерам. Кэш: `vin_power_cache.json`. Для корейских/европейских машин часто пусто.
2. **Локальная база** — `power_lookup.json`: марка, модель, год, объём → мощность. Можно дополнять вручную или из открытых баз.

Формула по объёму **не используется** (даёт неверные значения, например 3 л BMW X6 ≠ 165 л.с.).

## Формат power_lookup.json

Массив объектов. Поля:

- `make` / `brand` — марка (латиница или как в каталоге, например "벤츠" для Mercedes).
- `model` — модель (совпадение по вхождению: "X6", "3", "C").
- `year` — год (опционально).
- `displacement` — объём двигателя в см³ (опционально, строка или число).
- `power` / `horsepower` / `hp` — мощность в л.с. (число).

Пример:

```json
{"make": "BMW", "model": "X6", "displacement": "2998", "power": 306}
```

## Откуда брать данные

- Официальные каталоги производителей (BMW, Mercedes и т.д.).
- Открытые наборы: [CORGIS Cars](https://corgis-edu.github.io/corgis/csv/cars/), [fueleconomy.gov](https://www.fueleconomy.gov/), [Wikidata](https://www.wikidata.org/) (свойство P2109 — мощность).
- Скрипт для импорта из CSV можно добавить в `scripts/` (например, build_power_lookup_from_csv.py).

При экспорте вызывается `power_from_external.get_power_for_car(data)`: сначала NHTSA по VIN, затем поиск в `power_lookup.json`.

## США (Autotrader): `us_power.py` + `us_engine_map.json`

Autotrader в карточке отдаёт только строку `engineDescription` без л.с., поэтому полная таможня РФ
(нужны и `displacement_cc`, и `power_hp`) не считалась — карточки уходили в `price_on_request`.
Порядок подбора в `backend/us_power.py` (только для `source=autotrader|usa`, Корея/Китай не затрагиваются):

1. **NHTSA vPIC по VIN** — `https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{VIN}`;
   берём `EngineHP`/`EngineHP_to` (для акциза — максимум), `DisplacementCC`/`DisplacementL`,
   `ElectrificationLevel` (BEV). Кэш: `vin_power_cache.json` (`USA_VIN_POWER=0` — выключить,
   `USA_VIN_POWER_TIMEOUT` — таймаут, по умолчанию 6 с). Ожидаемое покрытие ~28%.
2. **`us_engine_map.json`** — кураторский каталог по марке/модели/объёму/топливу/годам;
   объём сравнивается по номиналу (кратно 100: 3496 → 3500), см. `engine_hp_resolver.normalize_cc_100`.
3. Общие слои `hp_catalog` → `power_lookup.json` (через `catalog_export_utils.fill_power_from_external`).

Формат записи (как в `engine_map.json`):

```json
{"make": "Ford", "model_substrings": ["f150", "f-150"], "cc": 3500, "fuel": "gas", "hp": 375, "year_min": 2015, "year_max": 2020, "priority": 9}
```

- `cc` — номинальный объём (2000, 3500, 5700, …), `fuel`: gas|diesel|hybrid|electric.
- `priority` — при совпадении нескольких записей (например, Escalade vs Escalade-V) выигрывает больший.
- Заполненные `power_source`: `vin_vpic` (vPIC) и `us_engine_map` (каталог); `power_estimated=true`.

Бэкфилл по БД: `python backend/scripts/backfill_usa_power.py --dsn "$DATABASE_URL"` (ставит
`needs_pricing_recompute=TRUE`), затем `postgres_catalog_sync` переоценивает таможню.

## Библиотека живёт дальше бэкфилла (ingest + рост)

`us_engine_map.json` — это **библиотека**, а не разовая заливка под текущий срез карточек:
она консультируется при каждом появлении новой машины, поэтому новые лоты получают мощность
без повторного бэкфилла.

1. **Ingest (Autotrader).** `parser.normalize_listing()` перед возвратом вызывает
   `us_power.enrich_usa_power_at_ingest(car)`: если в библиотеке нашлась запись
   make/model/cc/fuel/year, карточка сразу уходит в БД с `power_hp`/`displacement_cc`
   (`power_source=us_engine_map`). Слой офлайн (файл читается один раз, кеш по mtime+size),
   сеть не тормозит скрапер и не ломает парсинг (хук в try/except).
2. **vPIC на ingest — опция.** `USA_VIN_POWER_AT_INGEST=1` включает запрос по VIN прямо
   при парсинге; по умолчанию выключено — vPIC всё равно отработает в `postgres_catalog_sync`.
3. **Пустые ответы vPIC не «залипают»:** если vPIC не дал hp, VIN перезапрашивается через
   30 дней (`_VIN_CACHE_NOHP_TTL_SEC`), чтобы библиотека могла подрасти. Заполненные ответы
   живут ~13 месяцев (`_VIN_CACHE_TTL_SEC`).
4. **Рост библиотеки.** `python backend/scripts/usa_engine_map_suggest.py --dsn "$DATABASE_URL"`
   обходит карточки без мощности, тянет vPIC по VIN и печатает готовые записи для
   `us_engine_map.json` (`suggest_library_entries()`: `hp` — медиана наблюдений, `cc` —
   номинал кратно 100, `samples` — сколько VIN подтвердило, `year_min/year_max` — границы
   модельных годов, отсутствие годов означает «без границ»). Опции: `--source`,
   `--min-count` (минимум VIN на запись), `--no-vin` (без сети, только файловый кеш),
   `--json-out data/us_engine_map_candidates.json`, `--max-rows`.
   Добавлять записи в JSON под ревью → следующие карточки этой модели резолвятся офлайн.
5. **Проверка.** `backend/tests/test_us_power.py` — 23 теста: слои vPIC/каталога, TTL
   пустого кеша, ingest-хук (включая `normalize_listing`), рост библиотеки на временном JSON,
   агрегатор кандидатов. Корея/Китай не затрагиваются (`is_usa_source`).

