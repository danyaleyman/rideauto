# Deprecation: legacy-поля в ответах API

Цель: со временем опираться на **`read_model`** (detail) и на **развёрнутые** поля slim (`price`, `pricing_tier`, …), а дубли в `data.*` не использовать на фронте.

Даты — ориентиры для планирования; финальная дата может сдвигаться по мере готовности UI.

| Поле / область | Где видно | Замена | Не раньше (выключить зависимость) | Примечание |
|----------------|-----------|--------|-----------------------------------|------------|
| `data.my_price` как основная цена | slim `data`, detail `data` | slim: `price`; detail: `read_model.price_rub` + `read_model.price_on_request` | **2026-09-01** | `my_price` остаётся сырой валютой/черновиком; отображение — read model. |
| `data.power`, `data.hp`, `data.outputHorsepower` | slim `data` | `read_model.power_hp` на detail; в slim прямого read_model нет — запрос деталки или расширение API | **2026-09-01** | Дублируют мощность; read model нормализует в л.с. |
| `data.mark` / `model` / `generation` (сырой Encar) | slim `data`, detail `data` | **Список:** `title` + **`read_model`**. **Карточка:** только `read_model` + нормализованный `result.data` | **2026-12-01** | Плоский JSON в БД больше не дублирует марку/модель на корне `result` — всё в `data` + `read_model`. |
| `data.engine_type`, `transmission_type`, `body_type`, `color` (legacy RU) | slim `data` | `read_model.*` на detail; slim — по возможности заголовок/`title` | **2026-12-01** | Параллельно с миграцией на clean read. |
| `data.images` сырой формат (строка JSON vs list) | slim `data` | Стабилизировать на стороне API или отдать отдельным полем | **TBD** | Сейчас slim нормализует порядок/обрезку; клиентам не полагаться на «сырой» формат Encar. |
| Поиск `full=1` (полная строка БД в `result`) | `/api/search`, `/api/cars` | Явный internal/admin эндпоинт или отдельный контракт | **TBD** | Не считается стабильным публичным контрактом для витрины. |

## Миграция фронта (кратко)

1. **Список**: те же поля + **`read_model`** (дублирует логику карточки); не вычислять цену из `my_price`, если есть `price`.
2. **Карточка**: характеристики и цена — **`result.read_model`**; сырой слой — **`result.data`** (без полей на корне `result`, кроме `id` и флагов).
3. Следить за **`api_contract_version`** / **`api_version`** в meta и при смене версии сверяться с `docs/API_CONTRACT.md` и новыми golden в `tests/fixtures/api_contract/{version}/`.

Нарушение обязательных полей slim/detail теперь приводит к ошибке при сборке ответа (см. `fastapi_app/schemas/catalog_contract.py` и `slim_catalog_car` / `GET /api/car`).
