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
# С галереей со страницы /detail/{infoid} (доп. HTTP GET, как в браузере):
python scripts/che168_smoke_fetch.py --config ../che168_scraper.yaml --limit 2 --detail-html
```

Live checker (проставить `che168_listing_sold` в БД):

```bash
python scripts/che168_listing_live_checker.py --config ../che168_scraper.yaml --once
```

Daily update цикл (discover + remove sold + `--only-pending`):

```bash
python che168_daily_update.py --config ../che168_scraper.yaml --once
```

Глубина daily discover: `daily_update.new_list_pages_per_run` страниц с **начала** выдачи
(там появляются новые лоты) по **всем** брендам из `GET /brand` (`new_brand_sample: 0`;
`>0` — ротирующееся окно брендов, курсор в `scraper_checkpoint_state` `daily_brand_cursor`).
Если шаг `--only-pending` падает, цикл завершается с кодом **1** (а не молча «зелёным»).

## Полный обход каталога (сегментация)

`/search` отдаёт не больше ~50–100 страниц на один запрос, поэтому простой обход по брендам
видит лишь часть каталога (на проде 09–10.10.2025 — ~143k строк из ~235k, ≈60%).
Полный каталог достаётся дроблением на сегменты **price × year**:

```bash
# Полный обход без лимита (на проде — через systemd, см. ниже)
python che168_scraper.py --config ../che168_scraper.yaml --segmentation --max-cars 0

# Начать каталог с нуля: сбросить чекпоинты brand_*/segment_*
python che168_scraper.py --config ../che168_scraper.yaml --segmentation --reset-offsets
```

- Флаг `--segmentation` (`--full`) включает `che168.segmentation` без правки YAML
  (сегменты заданы в `che168_scraper.yaml`: 10 ценовых × 8 годовых).
- Чекпоинт бренда/сегмента, дошедший до конца выдачи, автоматически сбрасывается в начало
  (`che168.reset_offset_on_complete: true`) — иначе новые объявления в «голове» выдачи
  больше никогда не сканируются.
- На проде: `deploy/scripts/run_che168_scraper_full_host.sh`,
  юниты `rideauto-che168-scraper-full.service` + `rideauto-che168-scraper-full.timer`
  (еженедельно, `Sun 06:00 Asia/Yekaterinburg`, `Persistent=true`).
  Ручной запуск: `systemctl start rideauto-che168-scraper-full.service`.

Секреты и устройство:

- `che168.deviceid`: при пустом значении в YAML скрейпер **сгенерирует случайный UUID** (`ensure_che168_deviceid`); для стабильной долгой сессии лучше задать свой или `CHE168_DEVICE_ID`.
- Опционально: `che168.sessionid` / `che168.cookies` или Playwright bootstrap.
- Для непустой выдачи `/search` обычно нужен **валидный `sessionid`** (см. `che168_scraper.local.yaml` в `.gitignore`).

Прокси: блок `proxy` (`enabled`, `urls`). Для Che168 по умолчанию **`sticky_session: true`**: используется только **`urls[0]`** без ротации (иначе смена IP сбрасывает `sessionid`). После Playwright bootstrap клиент берёт **`che168._session_proxy_url`** — тот же URL, что и у Chromium. Ротацию можно включить **`sticky_session: false`** (не рекомендуется с живой сессией). Установка браузера: `pip install playwright && playwright install chromium`.

**Resilience Platform:** `http.transport: curl_cffi` + `http.impersonate` (Chrome TLS), Playwright только как SessionProvider. ADR: [`docs/adr/0002-scraper-resilience-hybrid.md`](../../docs/adr/0002-scraper-resilience-hybrid.md). Probe:

```bash
python scripts/resilience_probes.py --source che168 --config ../che168_scraper.yaml
```

Остановка: `SIGINT` / `SIGTERM` — list producer прекращает дальнейшие бренды/страницы (`stop_event`).

## API (эндпоинты)

База: `https://globalapi.che168.com/api/v1/` — клиент: `scraper_pipeline/che168/client.py`.

Реализованы вызовы: `/brand`, `/search`, `/carinfo/{id}`, `/specparam`, `/specconfig`, `/recommend`, `/report/summary` с параметрами `_appid`, `deviceid`, `language` и заголовками Origin/Referer под `global.che168.com`.

**Язык ingest:** всегда **`language=en`** (их перевод с китайского точнее). RU на сайте RideAuto — через EN→RU маппинг (`localization/term_localizer.py`, `facet_normalize`), без второго прогона API. Клиент принудительно нормализует `che168.language` в `en`.

Ответ `/carinfo` иногда кладёт галерею **рядом** с `result` (не внутри объекта карточки). Перед парсингом `merge_che168_api_carinfo_envelope` объединяет внутренний слой и такие соседние поля (`images`, `picurls`, …), иначе в каталоге остаётся только обложка.

Дополнительно выполняется **глубокий обход** всего JSON ответа `/carinfo` и поиск URL на CDN (`autoimg` / `escimg` / `erscglobal`), чтобы подхватить галереи под нестандартными ключами. Соцссылки дилера (`wa.me`, WeChat) отфильтровываются.

Если в `/carinfo` по-прежнему одна обложка, воркер при `che168.fetch_detail_gallery_html: true` запрашивает **HTML** страницы `{origin}/detail/{infoid}` (`che168.detail_page_url_template`) с теми же куками, что и API, и вытаскивает из разметки все `https://erscglobal*.autoimg.cn/escimg/...` — как в колонке Network → Img в браузере.

## Цена в ¥

- В каталоге для расчёта используется **`price_cny`** (полные юани). Сырой ответ API сохраняется в **`che168_price_raw`**.
- Если API отдаёт цену в **万元** как дробь (`12.8` → `128000`), включите `che168.assume_price_in_wan_yuan: true`.
- Иначе парсер применяет эвристики: малые значения (`12.8`, `25`), а также диапазон **1000–99999** (типичный Global API: `10770` = 10.77万 → `107700` ¥, правило `heuristic_medium_wan_x1000`).

## Очистка устаревших строк БД

Однократно для старых листингов с иным `source`: `deploy/scripts/sql/purge_obsolete_china_sources.sql`.

## Следующие шаги

- Уточнить форму ответов API под прод и при необходимости подправить `che168_search_items` / разбор полей в `parser.py`.
