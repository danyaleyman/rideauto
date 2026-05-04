# Che168 Global — цепочка Китая (изолированно от Кореи)

- **Корея:** `source = encar`, чекпоинт `scope = encar`, `backend/encar_scraper.py`, конфиг `scraper_config.yaml`.
- **Китай:** `source = che168`, `car_id` = `che168-<infoid>`, чекпоинт по умолчанию `scope = che168`, скрейпер `backend/che168_scraper.py`, конфиг **`che168_scraper.yaml`** в корне репозитория.

Сырой конверт в `cars.raw` / `data.raw_envelope`: `che168.raw.v1` (источники `list_item`, `carinfo`, `specparam`, `specconfig`, `recommend`, `report_summary`).

## Запуск

Из каталога `backend` (чтобы резолвились импорты):

```bash
python che168_scraper.py --config ../che168_scraper.yaml
```

Смоук на N машин:

```bash
python che168_scraper.py --config ../che168_scraper.yaml --max-cars 20
```

Проверка API **без Postgres** (сырые ответы + нормализация):

```bash
python scripts/che168_smoke_fetch.py --config ../che168_scraper.yaml --limit 5
```

Live checker (проставить `che168_listing_sold` в БД):

```bash
python scripts/che168_listing_live_checker.py --config ../che168_scraper.yaml --once
```

Секреты и устройство:

- В YAML: `che168.deviceid` (UUID), опционально `che168.sessionid` / `che168.cookies`.
- Либо окружение: `CHE168_DEVICE_ID` (подставится в `che168.deviceid`).
- Для непустой выдачи `/search` обычно нужен **валидный `sessionid`** (см. `che168_scraper.local.yaml` в `.gitignore`).

Прокси: блок `proxy` (`enabled`, `urls`). Для Che168 по умолчанию **`sticky_session: true`**: используется только **`urls[0]`** без ротации (иначе смена IP сбрасывает `sessionid`). После Playwright bootstrap клиент берёт **`che168._session_proxy_url`** — тот же URL, что и у Chromium. Ротацию можно включить **`sticky_session: false`** (не рекомендуется с живой сессией). Установка браузера: `pip install playwright && playwright install chromium`.

Остановка: `SIGINT` / `SIGTERM` — list producer прекращает дальнейшие бренды/страницы (`stop_event`).

## API (эндпоинты)

База: `https://globalapi.che168.com/api/v1/` — клиент: `scraper_pipeline/che168/client.py`.

Реализованы вызовы: `/brand`, `/search`, `/carinfo/{id}`, `/specparam`, `/specconfig`, `/recommend`, `/report/summary` с параметрами `_appid`, `deviceid`, `language` и заголовками Origin/Referer под `global.che168.com`.

## Цена в ¥

- В каталоге для расчёта используется **`price_cny`** (полные юани). Сырой ответ API сохраняется в **`che168_price_raw`**.
- Если API отдаёт цену в **万元**, включите в конфиге `che168.assume_price_in_wan_yuan: true`.
- Иначе парсер применяет эвристику для малых дробных значений (типа `12.8` → `128000`).

## Очистка устаревших строк БД

Однократно для старых листингов с иным `source`: `deploy/scripts/sql/purge_obsolete_china_sources.sql`.

## Следующие шаги

- Live checker: отдельный скрипт по аналогии с `encar_listing_live_checker.py` (HEAD/GET к `carinfo` или поиску).
- Уточнить форму ответов API под прод и при необходимости подправить `che168_search_items` / разбор полей в `parser.py`.
