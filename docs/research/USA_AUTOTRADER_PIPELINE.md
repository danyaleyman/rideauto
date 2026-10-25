# USA / Autotrader — план контура (MVP → полный)

## Продукт (зафиксировано)

- Источник: `autotrader.com` напрямую (не CarAPIs, не IAAI/Copart).
- Объём: все listingType, national SRP **без zip**.
- Глубина: **SRP + VDP** (полная комплектация / галерея с VDP).
- Изоляция: отдельный пакет + `source=autotrader` + `region=usa` (как encar/che168).

## Архитектура

```
backend/scraper_pipeline/autotrader/
  parser.py         # HTML → __NEXT_DATA__ → normalized car
  client.py         # GET SRP/VDP (+ cookie jar / UA), curl_cffi
  browser_ingest.py # двухфазный ingest: SRP → scraper_pending_ids → VDP (HTTP-first, Playwright fallback)
  session.py        # Playwright bootstrap cookies
  workers.py        # тонкая обвязка/совместимость
  runtime_stats.py  # статистика прогона
backend/autotrader_scraper.py
autotrader_scraper.yaml
```

## Сквозной поток данных (ingest → БД → каталог → цена)

### 1. Парсинг: SRP/VDP → нормализованная карточка

| Шаг | Код | Результат |
|-----|-----|-----------|
| Запуск | `backend/autotrader_scraper.py` → `scraper_pipeline/autotrader/workers.py` → `browser_ingest.run_autotrader_browser_ingest()` | Playwright-пул: SRP последовательно, VDP по `detail_concurrency` |
| SRP | `parser.parse_srp_page(html)` | `__NEXT_DATA__` → `pageProps.__eggsState` → `srp_results.activeResults` (id) + `inventory[id]` |
| VDP | `parser.parse_vdp_page(html, id)` | карточка из `eggs["inventory"][id]` (features, images, vin, …) |
| Нормализация | `parser.normalize_listing(listing)` | `car`: `source=autotrader`, `id=autotrader-{listingId}`, `price_usd`, `displacement_cc` («2.0L»→2000), `engine_type` (fuel), `vin`, `images`, `features`, `_raw` |

Из-за `require_vdp: true` в `autotrader_scraper.yaml` SRP-only карточки не сохраняются (ретраи VDP вместо «1 фото»).

### 1a. Двухфазный ingest (list → `scraper_pending_ids` → detail)

`browser_ingest.py` умеет работать в трёх режимах (`autotrader.phase`, CLI `--phase`):

| phase | Что делает | Нужен Postgres |
|-------|------------|----------------|
| `all` (по умолчанию) | discovery наполняет pending, параллельно воркеры его дренируют; без DSN — очередь в памяти | нет |
| `list` | только SRP → `scraper_pending_ids` (быстрый обход каталога, без VDP) | да |
| `detail` | только разбор pending (SRP не запрашивается) | да |

- CLI: `--phase {all,list,detail}`; `--only-pending` — то же, что `--phase detail` (`scraper_pipeline/autotrader/browser_ingest.py`, `_PHASE_ALIASES`).
- Очередь: `CheckpointAsync` (`scope=autotrader`) — те же таблицы, что у Encar/Che168 (`scraper_pending_ids`, `scraper_collected_ids`), поэтому супервизор видит `pending_autotrader`.
- Курсор SRP хранится в `scraper_checkpoint_state` (`get_last_offset("all")`) — рестарт продолжает с последней страницы (`resume_cursor: true`), «холостые» страницы (0 новых id) останавливают обход (`srp_stall_pages_limit`).
- Ретраи VDP: `vdp_retries` (попытки внутри жизни) + `vdp_max_attempts` (сколько раз карточка возвращается в pending); после исчерпания карточка закрывается в `scraper_collected_ids` (или сохраняется SRP-стаб, если `require_vdp=false` и `stub_on_vdp_fail=true`).
- Транспорт: `http_first` (curl_cffi) с автовыключением после `http_fail_disable` challenge-ов, `http_timeout_sec` — жёсткий wall-clock на запрос, `http_max_revives` — сколько раз HTTP оживает после свежих cookies из браузера.
- Запись: буфер `save_batch_size` / `save_flush_sec` → `bulk_save` одной транзакцией на пачку (как Encar), `mark_collected` — после коммита.
- Финальная строка лога различается: `Autotrader ingest done …` (плановый прогон) и `Autotrader only-pending done …` (`detail`) — супервизор считает по ней завершение.

Отказоустойчивость/supervisor:

- `deploy/scripts/rideauto_scraper_supervisor.py` видит `pending_autotrader` (0 = очередь разобрана) и применяет к США те же правила, что к Корее/Китаю: stall → restart; `pending == 0` + `ingest done`/`only-pending done` → рынок завершён.
- `WRA_SUPERVISOR_AT_PHASE=all|list|detail|only-pending` пиннит фазу без правки YAML (ops-режим: «добор pending» / «разбор хвоста»).
- `WRA_SUPERVISOR_AT_SPLIT=1` — два процесса (`--phase list` + `--phase detail`) вместо `phase=all`: SRP и VDP не делят один Chromium; у каждого detail-воркера sticky egress (`sticky_browser_slots`).
- Прокси: отдельный US residential пул (`AUTOTRADER_PROXY_URLS`), health-quarantine (`proxy.failure_threshold` / `quarantine_sec`). Не смешивать с `ENCAR_PROXY_URLS`. Не поднимать AT параллельно с полным дампом Encar на том же хосте.
- Стабильный потолок: `detail_concurrency: 2` (soft-cap 3 без `detail_concurrency_force`), `require_vdp: true`, `http_first: true`, `list_pause_when_pending_above: 5000`.

### 2. Ingest → Postgres (та же транзакция, что у Encar/Che168)

- `saver = build_car_saver(config)` → `PostgresCarSaver` (`storage.backend=postgres`, `store_raw_responses: true`, `count_cars_source: autotrader`).
- `save_car(car, car_id)` → `_save_sync()` → `_upsert_one()` (`scraper_pipeline/encar/savers.py:148`):
  1. `payload["_catalog_needs_pricing_recompute"] = True` — очередь пересчёта для ночного sync;
  2. `row_to_car_fields()` → денормализованные колонки: `power_hp` (= `spec.power_hp` либо `power_hp(payload)`), `displacement_cc`, `price_rub`, `year`, `source=autotrader`;
  3. `UPSERT_CAR_SQL` (`catalog_pg_core.py:399`) — `ON CONFLICT (car_id) DO UPDATE`; `needs_pricing_recompute = cars.… OR EXCLUDED.…` (ingest никогда не гасит очередь: `sync_clear_pricing_recompute_queue=False`);
  4. `car_images` — `DELETE` + `INSERT` по порядку галереи (`sort_order`, `is_primary=i==0`);
  5. `data` — JSONB полного payload, `raw` — gzip+base64 снапшот (`autotrader_raw_YYYY-MM-DD.jsonl`, retention 14 дней).

Итог ingest: карточка лежит в `cars` с `power_hp` (если его дала библиотека — см. §4), `price_usd` и `needs_pricing_recompute=TRUE`. Рубли/таможня на этом шаге не считаются.

### 3. Ночной catalog sync: цена, tier, сброс очереди

```
rideauto-catalog-pipeline.timer (03:30) → deploy/scripts/run_catalog_pipeline_host.sh
  1) run_postgres_catalog_sync_host.sh → python -u backend/postgres_catalog_sync.py --config scraper_config.yaml
  2) run_meilisearch_sync_host.sh (blue/green) + метрики wra_job_last_* + catalog_meili_consistency --strict
```

- **Отбор строк**: `SELECT id, car_id, data, raw, source_internal_id, needs_pricing_recompute FROM cars` → дедуп по `listing_key_for_export()` (побеждает max `id`), порции `--process-batch-size` (500).
- **Диспатчер рынка** (`postgres_catalog_sync.py:430`): `usa_market_car(car_id, data)` = `car_id LIKE 'autotrader-%'` **или** `source in (autotrader, usa)`. Только тогда работает `PriceCalculatorUsa(fx)` — Корея/Китай идут своими ветками.
- **Ветка США** (`postgres_catalog_sync.py:430-468`):
  | Ситуация | Что пишем |
  |----------|-----------|
  | нет `price_usd` (`usa_has_source_price` → `parse_price_usd() > 0`) | `price_on_request=true`, `pricing_tier="price_on_request"`, `clear_estimated_price_fields()`, `sync_usa_pricing_clean_block()` |
  | цена есть | `priceusa.update_usa_car_with_prices()` → см. §4 про `enrich_usa_power_if_needed()` → `usa_has_customs_inputs()` (EV: hp>0; ICE/hybrid: cc>0 **и** hp>0) → `calculate_total_cost_usa()` → `my_price`, `duty_rub`, `excise_rub`, `util_rub`, `vat_rub`, `customs_total_rub`, `commission_rub`, `pricing_tier="full_customs"` |
  | цена есть, но cc/hp не набрались | `price_on_request` (заглушек 2000 см³ / 0 л.с. нет), `usa_customs_inputs_missing=true` |
  | исключение в калькуляторе | `price_calc_failed=true` + `price_on_request` |
- **Обратный upsert**: тот же `UPSERT_CAR_SQL`, но `_catalog_needs_pricing_recompute=False` и `sync_clear_pricing_recompute_queue=not no_prices` → `needs_pricing_recompute=FALSE` (очередь закрыта) + `car_images`.
- **Версия правил**: блок `pricing_clean` хранит `USA_PRICING_RULES_VERSION` (`priceusa.py`, сейчас `2026.10.09`); итоговая сводка пишет `ok_usa / skipped_usa_no_price` и `needs_pricing_recompute` count.

### 4. Мощность: где берётся hp и как библиотека растёт

`us_power.fill_usa_power(car, allow_vin=…)` — работает **только** для `source in {autotrader, usa}` и не трогает карточку, если hp уже есть.

1. **NHTSA vPIC по VIN** (`lookup_vin_power`): кеш `data/vin_power_cache.json`; TTL 400 дней при найденном hp, **30 дней при пустом ответе** (чтобы библиотека могла подрасти, а VIN перезапросился). Из ответа берётся max(`EngineHP`, `EngineHP_to`), `DisplacementCC`/`DisplacementL`, признак BEV; при пустом `displacement_cc` он добирается, BEV получает `engine_type=Electric`. `power_source="vin_vpic"`.
2. **`data/us_engine_map.json`** через `engine_hp_resolver.resolve_hp_from_entries(..., normalize_cc=True, cc_override=usa_engine_cc(car))` — объём сравнивается по номиналу кратно 100 (3496→3500). `power_source="us_engine_map"`.

Точки вызова: ingest (`parser.normalize_listing`, офлайн) и pricing (`priceusa.enrich_usa_power_if_needed` → ещё и общие слои `hp_catalog`/`power_lookup`). Кеш каталога — по `(mtime_ns, size)`, сброс — `invalidate_us_engine_map_cache()`.

Рост библиотеки (vPIC = «слой роста»):

```bash
python backend/scripts/usa_engine_map_suggest.py --dsn "$DATABASE_URL"       # с vPIC по VIN
python backend/scripts/usa_engine_map_suggest.py --dsn "$DATABASE_URL" --no-vin
```

Скрипт берёт карточки без мощности, подтверждает их по VIN и печатает кандидатов `suggest_library_entries()` (hp — медиана, cc — номинал, `samples`, `year_min/max`). Ревью → merge в `data/us_engine_map.json` → следующие ingest/sync получают hp без сети. Исторический хвост добивается `backend/scripts/backfill_usa_power.py` (`--no-vin`, `--dry-run`), который ставит `needs_pricing_recompute=TRUE`, после чего следующий sync пересчитывает таможню.

### 5. Изоляция от Кореи/Китая

- Гейт `us_power.is_usa_source()` + `US_SOURCES` — enricher не срабатывает на `encar`/`che168`.
- `usa_market_car()` в диспатчере цен — китайские/корейские ветки не меняются.
- `engine_map.json` / `auto_learn_engine_map.py` (пишется при `AUTO_LEARN_ENGINE_MAP=1`, берёт только карточки с `power_source != engine_map`) — отдельный контур Кореи; США используют собственный `us_engine_map.json`.

## Контракт данных

| Шаг | URL | Данные |
|-----|-----|--------|
| List | `GET /cars-for-sale/all-cars?page={n}` | `srp_results.activeResults` + `inventory[id]` |
| Detail | `GET /cars-for-sale/vehicle/{id}` | `inventory[id]` (features, images×N, vin, …) |
| id | | `autotrader-{listingId}` |

Нормализованный payload кладётся в `cars.data` через общий `PostgresCarSaver`; `source=autotrader`.

Цена: `price_usd` в data (+ `needs_pricing_recompute`). FX USD→RUB / калькулятор USA — отдельный follow-up (`priceusa.py`), не блокер ingest.

## Антибот / сессия (без ручных cookie)

Akamai (`_abck`, `bm_*`). Канон для прода:

1. **Playwright bootstrap** (`scraper_pipeline/autotrader/session.py`) открывает SRP, забирает cookies.
2. Cookies кэшируются в `autotrader.session_file` (по умолчанию `/var/lib/rideauto/autotrader_session.json`, TTL ~6ч).
3. Массовый fetch идёт через **curl_cffi** (Chrome JA3) + эти cookies; на challenge — refresh bootstrap.
4. С датацентрового IP Akamai часто режет — задайте **residential proxy** один раз: `AUTOTRADER_PROXY_URL` или `autotrader.bootstrap_proxy_url` (как FloppyData для Encar). После этого daily/full scrape без ручных Cookie.

Опциональный override: `AUTOTRADER_COOKIE` (не нужен в нормальной эксплуатации).

Парсер покрыт unit-тестами на fixtures; live без proxy может 403.

## Статус реализации (код)

| Компонент | Путь | Статус |
|-----------|------|--------|
| Parser / client / workers | `backend/scraper_pipeline/autotrader/` | ✅ |
| Двухфазный ingest (`--phase`) | `backend/scraper_pipeline/autotrader/browser_ingest.py` | ✅ |
| Entrypoint + YAML | `backend/autotrader_scraper.py`, `autotrader_scraper.yaml` | ✅ |
| Parser tests | `backend/tests/test_autotrader_parser.py` | ✅ |
| Supervisor (3 рынка, `pending_*`) | `deploy/scripts/rideauto_scraper_supervisor.py` + systemd unit | ✅ |
| Покрытие SRP: срезы / потолок глубины / телеметрия | `browser_ingest.build_segments`, `_walk_segment`, `runtime_stats` | ✅ (2026-10-25) |
| Pricing USA | `backend/priceusa.py` + hooks in catalog sync | ✅ |
| HP-библиотека США | `backend/us_power.py`, `data/us_engine_map.json` | ✅ |
| Catalog `region=usa` | Meili filter, URL/market maps, SEO/i18n | ✅ |
| Home carousel USA | stub, **catalogDisabled** до наполнения | ✅ |

### Каталог / VDP

- `fetch_vdp: true` + `require_vdp: true` + `vdp_retries` — не сохраняем SRP-only при таймауте VDP (ретраи вместо «1 фото»).
- Meili sync **не индексирует** Autotrader без VDP (`autotrader_depth=vdp` или ≥3 фото + ≥5 фич); строки остаются в Postgres.
- UI: `web/src/lib/autotrader-options-display.ts` — EN→RU комплектация.

### Мощность и таможня (power)

- `backend/us_power.py`: vPIC по VIN (кеш `data/vin_power_cache.json`) → `data/us_engine_map.json`
  (объём сравнивается по номиналу кратно 100) → общие слои hp_catalog/power_lookup. Только `source=autotrader|usa`.
- Хук: `priceusa.enrich_usa_power_if_needed()` (из `update_usa_car_with_prices` и `usa_has_customs_inputs`).
- **На ingest**: `parser.normalize_listing()` вызывает `us_power.enrich_usa_power_at_ingest(car)` —
  новая карточка попадает в БД сразу с `power_hp` из `us_engine_map.json` (офлайн, без сети).
  vPIC на ingest только при `USA_VIN_POWER_AT_INGEST=1`; иначе его добьёт catalog sync.
- Пустой ответ vPIC кешируется не навсегда: `_VIN_CACHE_NOHP_TTL_SEC` (30 дней) — библиотека
  может подрасти, и VIN перезапросится.
- **Рост библиотеки**: `python backend/scripts/usa_engine_map_suggest.py --dsn "$DATABASE_URL"`
  сканирует карточки без мощности, берёт vPIC по VIN и печатает кандидатов
  (`suggest_library_entries()`: hp — медиана наблюдений, cc — номинал, `samples` — сколько VIN подтвердило).
  Новые записи добавляются в `data/us_engine_map.json` под ревью → следующие карточки этих моделей
  получают мощность уже на ingest.
- Бэкфилл: `python backend/scripts/backfill_usa_power.py --dsn "$DATABASE_URL"`, затем `postgres_catalog_sync`.
- Формат каталога и переменные окружения (`USA_VIN_POWER`, `USA_VIN_POWER_TIMEOUT`,
  `USA_VIN_POWER_AT_INGEST`): `data/README_power.md`. Тесты: `backend/tests/test_us_power.py` (23).

### Ещё follow-up

- Daily update / prometheus / live checker
- Пополнять RU-маппинг по живым VDP (хвост unmapped EN)
- **Egress США**: US mobile/residential-пул или scraping API, проходящий Akamai (сейчас блок, см. «Покрытие выдачи США»)
- Проверить `autotrader.srp_num_records: 100` на живой выдаче, когда она откроется (сейчас 25 лотов/стр)

## Покрытие выдачи США (замер 2026-10-25)

### Почему каталог США «срезался»

| Симптом | Факт из прод-логов / БД |
|---------|--------------------------|
| Каталог почти пуст | `cars` (`source=autotrader`) = **675** при `total` выдачи **3 468 733** (fixture) / **3 523 823** (прод, окт.) — 0.02 % |
| Курсор SRP не сбрасывался | `list_offset_all` рос 13 → 748 → 778, после рестарта обход сразу упирался в «конец выдачи»; голова выдачи (новые лоты) не сканировалась |
| Потолок глубины считался сбоем сети | страницы 773–778 отдают HTML без `__NEXT_DATA__` → 5 ретраев + `recover_access` на каждую; прогон = 6 «мёртвых» страниц, `list_pages_ok=0` |
| Покрытие никто не считал | `ids/total` не логировался; «каталог стабилизировался» печаталось при живых 3.4 млн лотов |
| США «замирали» навсегда | supervisor помечал `autotrader.complete` после первого прохода и больше рынок не поднимал (`AT_IDLE_STOP`) |

### Что теперь в коде

| Механизм | Где | Поведение |
|----------|-----|-----------|
| Срезы SRP (`make` × `price` × `year`) | `autotrader.segmentation`, `build_segments()` | фильтры + отдельный курсор `srp:<name>` на срез; `max_segments` ограничивает |
| Адаптивное дробление | `split_segment()`, `adaptive_split` | срез шире `depth_cap_pages × page_size` дробится по цене, затем по годам (до `max_split_depth`) |
| Потолок глубины | `depth_limit_streak` | 2 страницы подряд без `__NEXT_DATA__` = конец выдачи среза (без 5 ретраев и recover), срез помечается `TRUNCATED` |
| Возврат курсора | `reset_cursor_on_complete` | закрытый срез на следующем проходе начинается с 1-й страницы (свежие лоты в голове); при квоте курсор идёт глубже |
| Квота на срез | `segment_max_pages` | 12 стр × 25 лотов ≈ 300 лотов/срез за проход (VDP — узкое место); 72 среза ≈ 21.6k лотов/проход |
| Телеметрия покрытия | лог + `scraper_checkpoint_state` | `SRP[<name>] срез закрыт … coverage=..%`, `Autotrader coverage: slices … ids … total … coverage … truncated … blocked … gaps`; ключи `srp_coverage_pct`, `srp_ids_total`, `srp_total_all`, `srp_truncated_slices`, `srp_blocked_slices` |
| WAF back-off | `block_abort_after` (8) | страница `page unavailable` = блок (не капча/не глубина): после 8 подряд проход закрывается (`WAF-BLOCKED`), курсоры не сдвигаются |
| Классификация блока | `client.is_autotrader_waf_block()`, `AutotraderWafBlock` | проверяется **до** challenge и на транспортном уровне (`_HttpGate`, `_BrowserPool.goto`): HTTP-блок не поднимает Chromium, браузерный — не тратит challenge-ретраи на страницу |
| Пауза после блока | `WRA_SUPERVISOR_AT_WAF_BACKOFF_SEC` (3600) | supervisor распознаёт закрытый блоком проход (`list_pages_ok=0` + `srp_waf_blocks>0` в последней статистике) и не перезапускает его каждую минуту; `pending>0` при этом поднимает только detail. Пауза пишется маркером `autotrader.waf_pause` и переживает рестарт юнита (не превращается в суточную), а «all markets complete» больше не уводит процесс в вечный idle — повторный проход стартует сам |

| Повторный проход США | `WRA_SUPERVISOR_AT_RERUN_SEC` (86400) | после COMPLETE рынок перезапускается через сутки (маркер `autotrader.complete` истекает), а не «навсегда» |

### Как проверить покрытие

```bash
# 1) Что реально отдаёт выдача (ничего не пишет в очередь и не трогает курсор)
.venv/bin/python backend/autotrader_scraper.py --config autotrader_scraper.yaml \
  --probe-url 'https://www.autotrader.com/cars-for-sale/all-cars' \
  --probe-url 'https://www.autotrader.com/cars-for-sale/all-cars?minPrice=0&maxPrice=20000&startYear=2015&endYear=2026'

# 2) Покрытие в логе прогона
grep -aE 'SRP\[|Autotrader coverage' logs/autotrader_*.log | tail -30

# 3) Покрытие в чекпоинте
docker exec rideauto-postgres-1 psql -U wra -d wra -tAc \
  "select key, value from scraper_checkpoint_state where scope='autotrader' and key like 'srp_%'"
```

Норма: `coverage` по срезу ≥ `min_coverage_ratio` (85 %) либо явный `QUOTA`/`TRUNCATED`.
`WAF-BLOCKED` в строке среза = выдача не отдалась вообще (см. блокер ниже).

### Блокер (инфраструктура): Akamai WAF, замер 2026-10-25 09:50–10:20 MSK

- `GET /cars-for-sale/all-cars` → `200`, **3 761 B**, `<title>Autotrader - page unavailable</title>`, тело «Incident Number: 18.5cce…» — WAF-блок, не капча;
- то же для `/cars-for-sale/vehicle/{id}` и `/rest/lsc/modelinfo/{id}` (1 из 3 VDP-запросов прошёл: 510 437 B с `__NEXT_DATA__` — блок вероятностный);
- `robots.txt` → `200 / 19 675 B` на всех выходах (сеть и прокси живы);
- egress: прямой выход прод-хоста (DE) **и** 22 сессии FloppyData (US 6, CA 3, KR 5, GB 2, MX 1, AU 1, DE 1, 3 таймаута) — одинаковый блок;
- отпечатки curl_cffi `chrome131/124/120/110`, `edge101`, `safari17_2_ios` — **0/20** успешных SRP;
- Playwright (headless Chromium + US-прокси): `page.goto` по SRP не завершается за 75–90 с; прогрев главной → SRP не помогает.

Вывод: контур и контроль покрытия готовы, но **нужен рабочий egress/отпечаток** — US mobile/residential-пул, который проходит Akamai на autotrader.com (или scraping API поверх Autotrader). Пока его нет, США физически не могут наполниться; при этом контур больше не крутит recover вхолостую: блок классифицируется на транспортном уровне, проход закрывается за ~3 мин (`WAF-BLOCKED`, 8 блоков подряд), а supervisor не перезапускает его каждую минуту — пауза `WRA_SUPERVISOR_AT_WAF_BACKOFF_SEC` (1 ч) и суточный `WRA_SUPERVISOR_AT_RERUN_SEC`.

Замер после правок (прод, 2026-10-25 11:48–11:51 MSK): 4 блока по HTTP (без Chromium) → HTTP-гейт отключился → 4 блока браузером → `проход закрыт`, `coverage: slices=1 processed=1 ids=0 blocked=1`, весь проход **168 с** вместо часов ретраев.

Цикл повторов проверен на проде 2026-10-25 12:24–12:30 MSK с временным `WRA_SUPERVISOR_AT_WAF_BACKOFF_SEC=120`: `WAF-пауза (marker autotrader.waf_pause) до 12:24:05` → `старт нового прохода (COMPLETE истёк)` → блок за 3 мин → `пауза до 12:27:43` → снова старт. Рестарт юнита сохраняет дедлайн паузы (не 24 ч), «all markets complete» не уводит в вечный idle.


### Почему дело не в отсутствии US-IP (замер 2026-10-25 12:20 MSK)

- `var/_us_pool_matrix.py` по всем 22 кредам FloppyData: **7 выходят из US** (PA, OR, GA, NC, MN, NJ), остальные — CA/MX/GB/DE/KR/AU;
- `var/_us_srp_check.py`: все 7 US-выходов × 2 отпечатка (`chrome131`, `safari17_2_ios`) → `200`, **3 760–3 762 B**, `page unavailable` — блок одинаковый, IP-пул просто «прожжён» Akamai;
- `var/_us_geo_matrix.py`: Smart Parameters FloppyData (`USER-type-residential-country-US[-session-X]`, синтаксис из их доков `proxies/basics.mdx`) на текущих сабюзерах дают **`407 CONNECT tunnel failed`** — шлюз принимает только базовый username. Значит `type-mobile` / `state` / `session` через эти креды недоступны, и «переехать на mobile» без ключа нельзя.

Что нужно запросить/сделать (в порядке цены и трудозатрат):

| Вариант | Что нужно | Замечания |
|---------|-----------|-----------|
| FloppyData **mobile** US (доверие выше residential) | Client API key → `POST /v2/proxy/rotating/connections` `{type:"mobile",country:"US"}` **или** сабюзер с разрешёнными smart params | ключ: `app.floppydata.com/api-keys`; в `.env` положить `AUTOTRADER_PROXY_URLS=<connectionString>` |
| FloppyData **Web Unlocker / Web Data** | тот же ключ, `POST /v1/webUnlocker` / `POST /v2/web-data/fetch` `{url, countryCode:"US", difficulty:"high"}` | даёт готовый HTML в обход Akamai; тариф отдельный, нужен новый транспорт в `_HttpGate` |
| Сторонний scraping API | аккаунт (ZenRows/ScraperAPI/Bright Data…) | тот же транспорт, ключ в `.env` |
| Другой US-пул | список прокси | проверить `var/_us_srp_check.py` до подключения |

Готовые диагностические скрипты (лежат в `var/` — каталог не в git, на хост копируются вручную; запуск с `set -a; . /etc/default/rideauto; . /opt/rideauto/.env; set +a`):

```bash
.venv/bin/python var/_us_pool_matrix.py   # какие креды дают US и принимают ли smart params
.venv/bin/python var/_us_srp_check.py     # отдаёт ли SRP через US-выходы (WAF/OK)
.venv/bin/python var/_us_geo_matrix.py    # матрица smart-параметров по одной паре кредов
```



