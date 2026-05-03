# Блок D — поэтапный clean read (10 → 50 → 100%)

Цель: безопасно включать **`build_catalog_read_model(..., use_clean=True)`** для части карточек, сравнивать с legacy на выборке и **откатывать флагами** без деплоя кода.

## Механика в коде

| Переменная | Эффект |
|------------|--------|
| `WRA_CLEAN_READ_MODE=1` | Мастер-включатель: rollout и выбор `use_clean` имеют смысл. При `0` clean выключен для всех ключей. |
| `WRA_CLEAN_READ_PERCENT=0…100` | Доля карточек с `use_clean=True`: **детерминированно** по `sha1(car_id)` (см. `clean_mode.clean_read_enabled_for_key`). |
| `WRA_LEGACY_FALLBACKS_ENABLED=1` | Внутри read model разрешён **fallback** с `*_clean` на legacy-поля при пустых clean (см. `read_models._pick`). На этапе канарейки обычно оставляют `1`. |

Где применяется `clean_read_enabled_for_key`:

- карточка: `fastapi_app/routers/car.py`;
- список/гидратация: `fastapi_app/catalog_slim.py`, `fastapi_app/routers/search.py`;
- материализация полей в БД при upsert: `catalog_pg_core.row_to_car_fields` (для согласованности колонок с JSON).

## Последовательность rollout (рекомендуемая)

1. **Staging**: `WRA_CLEAN_READ_MODE=1`, `WRA_CLEAN_READ_PERCENT=100`, прогнать dual-run и аудит.
2. **Prod canary**: `WRA_CLEAN_READ_PERCENT=10` (или 5), наблюдать 24–48 ч.
3. **Prod 50%**: `WRA_CLEAN_READ_PERCENT=50`.
4. **Prod 100%**: `WRA_CLEAN_READ_PERCENT=100`.
5. **После стабилизации** (например 14 дней на 100%): можно рассмотреть `WRA_LEGACY_FALLBACKS_ENABLED=0` — только после отдельной проверки (блок F/G).

## Go / No-Go перед повышением процента

- `backend/scripts/encar_parser_audit.py --fail-on-regression` → код **0** (на целевой БД / лимиты порогов как в prod).
- `backend/scripts/dual_run_clean_vs_legacy.py --limit 500` — смотреть `pct_rows_with_any_diff` и `by_field` (нет ли всплеска по цене / марке / КПП).
- При необходимости жёсткий порог в CI или ночном job:  
  `python backend/scripts/dual_run_clean_vs_legacy.py --limit 1000 --max-row-diff-pct 2` → код **0** только если не более 2% строк с любым отличием.

## Сравнение clean vs legacy

```bash
cd /path/to/rideauto/backend
export DATABASE_URL='postgresql://…'
python scripts/dual_run_clean_vs_legacy.py --limit 500
```

Резюме в **stderr**, полный JSON (stats + sample) в **stdout**.

### Режим `full` vs `--semantic`

В режиме по умолчанию (**full**) сравниваются **все** поля read model. На Encar это почти всегда даёт «отличия» по **mark/model/топливо/КПП/кузов/цвет**: legacy часто **локализован (RU)**, а `spec_clean` / `identity_clean` держат **корейские строки** с площадки — это **не регресс rollout**, а ожидаемый шум.

Для **Go/No-Go перед повышением `WRA_CLEAN_READ_PERCENT`** используйте:

```bash
python scripts/dual_run_clean_vs_legacy.py --limit 500 --semantic
```

Тогда учитываются только: **цена, tier, флаги цены, таможня, страховые поля, привод, power_hp**.

Опции:

- `--semantic` — режим выше (рекомендуется для канарейки).
- `--fail-on-diff` — код **2**, если есть **хотя бы одна** строка с отличием (в выбранном режиме).
- `--max-row-diff-pct N` — код **2**, если доля строк с отличием **> N** (0–100); `-1` отключает проверку (по умолчанию).
- `--source encar` — фильтр `cars.source` (по умолчанию `encar`).

## Переменные окружения: сессия или файл

- **`export DATABASE_URL=...`** в интерактивном shell действует **только до закрытия этой сессии**. Для разовой проверки этого достаточно.
- Для постоянства на сервере: строка уже в **`/etc/default/rideauto`**; перед ручным запуском можно  
  `set -a; source /etc/default/rideauto; set +a`  
  (от **root** или пользователя с правом чтения файла).
- **`PYTHONPATH`** для этого скрипта **не обязателен**, если запуск из каталога **`…/backend`**: скрипт сам добавляет корень `backend` в `sys.path`.

## Откат (без релиза)

| Ситуация | Действие |
|----------|----------|
| Нужно мгновенно выключить clean для всех | `WRA_CLEAN_READ_MODE=0` или `WRA_CLEAN_READ_PERCENT=0` |
| Вернуть только часть трафика | Уменьшить `WRA_CLEAN_READ_PERCENT` (например 50 → 10) |
| «Пустые» поля из-за отключённого fallback | Временно `WRA_LEGACY_FALLBACKS_ENABLED=1` |

Перезапуск API / обновление env в compose: по вашему деплою; кэш Redis сменит ключи при изменении ответа — при необходимости смените префикс `WRA_REDIS_CACHE_PREFIX` или TTL.

## Связанные документы

- Краткий чеклист: `backend/docs/PRODUCT_READY_ROLLOUT.md`
- Слои данных и версии: `backend/docs/BLOCK_0_SINGLE_SOURCE_OF_TRUTH.md`
- Цены и `pricing_clean`: `backend/docs/PRICING_PIPELINE.md`
