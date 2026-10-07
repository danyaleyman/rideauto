# USA / Autotrader — план контура (MVP → полный)

## Продукт (зафиксировано)

- Источник: `autotrader.com` напрямую (не CarAPIs, не IAAI/Copart).
- Объём: все listingType, national SRP **без zip**.
- Глубина: **SRP + VDP** (полная комплектация / галерея с VDP).
- Изоляция: отдельный пакет + `source=autotrader` + `region=usa` (как encar/che168).

## Архитектура

```
backend/scraper_pipeline/autotrader/
  parser.py      # HTML → __NEXT_DATA__ → normalized car
  client.py      # GET SRP/VDP (+ cookie jar / UA)
  workers.py     # list pages → detail queue → save
  runtime_stats.py
backend/autotrader_scraper.py
autotrader_scraper.yaml
```

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
| Entrypoint + YAML | `backend/autotrader_scraper.py`, `autotrader_scraper.yaml` | ✅ |
| Parser tests | `backend/tests/test_autotrader_parser.py` | ✅ |
| Pricing USA | `backend/priceusa.py` + hooks in catalog sync | ✅ |
| Catalog `region=usa` | Meili filter, URL/market maps, SEO/i18n | ✅ |
| Home carousel USA | stub, **catalogDisabled** до наполнения | ✅ |

### Ещё follow-up

- Live cookie/Akamai: `AUTOTRADER_COOKIE` / cookie_file при первом прогоне
- Включить кнопку каталога на home (`catalogDisabled: false`) после первых сохранений
- Daily update / prometheus / live checker
