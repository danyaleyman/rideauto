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
