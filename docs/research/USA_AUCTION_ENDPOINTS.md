# USA market — Autotrader (прямой ingest)

## Решение (2026-10-06)

| Источник | Статус | Почему |
|----------|--------|--------|
| **IAAI** | **нерабочий вариант** | Нет публичного vehicle JSON API. Search/detail = SSR HTML + Incapsula/Kasada. HTML-парсинг + постоянная ломка антибота — **нерационально** для RideAuto. |
| **Copart** | **нерабочий вариант** | Тот же класс (аукцион + антибот). Не рассматриваем. |
| **CarAPIs** | **не используем** для USA | Идём **напрямую** на Autotrader.com. |
| **Autotrader.com** | **основной USA source** | Есть JSON XHR; собираем контракт сами из браузера. |

Свитчер Корея/Китай на фронте **не трогаем**. США = отдельный `market`/`source` после готовности ingest.

---

## Почему не IAAI / Copart (и почему не HTML)

- Список: `POST /Search` → **HTML**, не API; ids в cookies (`vehicleItemIds`).
- Карточка: Fetch/XHR пустой по машине (`GetGBPUserLogin` → `""`); данные только в Document HTML.
- Антибот Imperva/Kasada (`reese84`, `incap_ses_*`) — сессия браузера обязательна и хрупкая.
- Вывод: **не API-источник**. Парсить HTML можно технически, но поддержка и риск блокировок не окупают salvage-каталог на старте USA.

Краткий архив IAAI Search — в конце файла (на случай если когда-то понадобится).

---

## Autotrader — сбор эндпоинтов

### Порядок

1. DevTools → Network → **Fetch/XHR** на `autotrader.com/cars-for-sale/...`
2. Сценарии: список → page 2 → фильтр year/make → карточка лота → галерея
3. В git только URL + ключи полей; **без** значений cookie / api-key / HAR с секретами
4. Сырьё: `docs/research/usa-samples/` (gitignored)

### Чеклист

- [x] Главный **search / listings** — Doc `__NEXT_DATA__` на SRP (`srp_results` + `inventory`)
- [x] Пагинация — `?page=2` … (`srp_srpPaginationLinks`)
- [ ] Фильтр year или make (снять отдельно при необходимости)
- [x] **Detail** — Doc `__NEXT_DATA__` → `__eggsState.inventory[listingId]` (полный лот)
- [x] VDP REST: payments / similar / modelinfo / getDealerInfo (дополнения)
- [x] Галерея — `images.sources[]` (VDP много; SRP часто 1 thumb)
- [x] Отсеять служебные XHR (ads / consent / pep / `_next/static/chunks`)

### Целевой маппинг

| Поле у нас | Откуда (VDP) |
|------------|--------------|
| `source` | `autotrader` |
| `car_id` | `autotrader-{inventory.id}` |
| title / year / make / model | `listingTitle`, `year`, `make.name`, `model.name` |
| price (USD) | `pricingDetail.salePrice` |
| vin | `vin` |
| images[] | `images.sources[].src` |
| listing status | `listingType` (New/Used/…) |
| location | `owner.location.address` (city/state/zip) |

---

## Найденные эндпоинты (2026-10-06, SRP all-cars)

Контекст: `Referer: https://www.autotrader.com/cars-for-sale/all-cars`

### 1) searchoptions — справочник фильтров (полезен)

```text
Site: autotrader
When: открыт SRP all-cars (на загрузке часто 2 одинаковых вызова)
Method: GET (curl без body)
URL: https://www.autotrader.com/cars-for-sale/bonnet-reference/searchoptions
Auth/cookies: browser session (имена: ATC_ID, JSESSIONID, _abck, bm_*, ak_bmsc — values NEVER in git)
Request notes:
  content-type: application/json
  Referer: /cars-for-sale/all-cars
Response: TBD (ожидаем JSON опций фильтров: make/model/year/body/… — прислать ключи Response)
Role: facets / search options reference — ДА для каталога (справочники)
  НЕ список объявлений
```
### 2) pep — персонализация / ads (НЕ каталог)

```text
Site: autotrader
When: SRP all-cars
Method: GET
URL: https://www.autotrader.com/cars-for-sale/pep
  ?pixallId=…&zip=undefined&pc.origin=srp&bu=atc&app=web&catalog=atc
  &includeRaw=true
  &includeSources=consumerAdTargets,activeExperiments,…
  &pc.locales=en
Auth: cookies + header x-api-key: undefined (в этом захвате)
Role: Pixall / targeting / experiments — НЕТ для каталога машин
```

### 3) cookielaw CDN — согласие cookies (игнор)

```text
https://cdn.cookielaw.org/consent/.../en.json
https://cdn.cookielaw.org/consent/.../<id>.json
Role: OneTrust consent — НЕТ
```

**Важно:** `searchoptions` / `pep` — не listings.

### Архитектура (из Network UI, 2026-10-06)

Сайт SRP — **Next.js** (`/cars-for-sale/_next/static/chunks/…`).  
Большинство строк в Network с фильтром `js` — это **бандлы UI**, не каталог. Их можно игнорировать.

Есть **динамический route** карточки: chunk `pages/.../[listingId]-….js` → URL лота с numeric `listingId`.

#### 4) vehicle detail — `_next/data/.../vehicle/<listingId>.json`

```text
Site: autotrader
When: SRP hover/prefetch карточки
Method: GET
URL:
  https://www.autotrader.com/cars-for-sale/_next/data/<buildId>/vehicle/<listingId>.json
  ?allListingType=all-cars&clickType=listing&listingId=<listingId>
Captured buildId: DMtxp8TuabMHtTRVKRsSd
listingId examples: 792361455, 792414750
Request headers seen:
  x-nextjs-data: 1
  x-middleware-prefetch: 1
  purpose: prefetch
Response (prefetch):
  200 OK
  content-length: 2
  body: {}                    ← пустой объект (hex 7B 7D)
  x-middleware-skip: 1
  x-matched-path: /vehicle/[listingId]
  x-powered-by: Express
Role: URL-паттерн detail ВЕРНЫЙ, но prefetch НЕ отдаёт данные.
      Next.js middleware на prefetch специально возвращает {}
      (оптимизация Soft Navigation / skip data load).
```

**Вывод:** эти два запроса с SRP — **не источник машины**. Реальные `pageProps` приходят при **полном** заходе на карточку (без `x-middleware-prefetch`).

#### 5) Список SRP — `__NEXT_DATA__` all-cars (разобран)

Файл: `all-cars.txt` (~3.7 MB HTML). Sample: `docs/research/usa-samples/autotrader-srp-all-cars-next-data.json` (gitignored).

```text
GET https://www.autotrader.com/cars-for-sale/all-cars
GET https://www.autotrader.com/cars-for-sale/all-cars?page=2   ← page 2…
page route: /[[...searchresults]]
pageType: srp
buildId: KZwXc8oktCo_UL3kmiK10
```

**Структура:**

```text
props.pageProps.__eggsState.srp_results
  .activeResults: [listingId, …]     # 25 ids на странице (int)
  .count: 3468733                    # всего лотов
  .stats: { year/mileage/derivedprice min-max-avg }

props.pageProps.__eggsState.inventory
  "{listingId}": { …card fields… }   # 25 из activeResults + ~13 spotlight/extra

props.pageProps.__eggsState.owners
  "{dealerId}": { … }                # дилеры для карточек

props.pageProps.__eggsState.srp_srpPaginationLinks.links
  [ { page: 1, href: "/cars-for-sale/all-cars" },
    { page: 2, href: "/cars-for-sale/all-cars?page=2" }, … ]
```

SRP card уже содержит **vin, pricingDetail, year/make/model, 1 image, ownerId** (~62 поля).  
VDP inventory богаче (~107 полей, полная галерея ~19 фото).

**Ingest list loop (черновик):**

1. `GET /cars-for-sale/all-cars?page={n}` (+ cookies Akamai/`_abck` как в браузере).
2. Parse `__NEXT_DATA__` → для каждого id в `srp_results.activeResults` взять `inventory[id]`.
3. Опционально enrich: `GET /cars-for-sale/vehicle/{id}` для полной галереи.
4. Стоп: `page * 25 >= count` или пустой `activeResults`.

Фильтры: `srp_filters` (zip, searchRadius, make, …) — query params на URL; точный контракт фильтров можно доснять позже.


---

## Найденные эндпоинты (2026-10-06, VDP — vehicle detail page)

Контекст (Referer):

```text
https://www.autotrader.com/cars-for-sale/vehicle/789850281
  ?allListingType=all-cars&zip=02645&clickType=spotlight
```

- **listingId** (наш `car_id`): `789850281`
- Cookies гео: `ATC_USER_ZIP`, `ATC_USER_RADIUS` (zip/radius для UI)

### 6) REST LSC — modelinfo (справочник модели, не лот)

```text
Site: autotrader
When: VDP listing 789850281
Method: GET
URL: https://www.autotrader.com/rest/lsc/modelinfo/487332
Path id: 487332  ← catalog/model id, НЕ listingId 789850281
Headers:
  content-type: application/json
  x-fwd-svc: atc
Role: specs/trim/model metadata (LSC backend) — частично ДА
      цена/VIN/фото конкретного лота — другой `/rest/lsc/…` или SSR
Response keys: TBD
```

### 7) KBB consumer reviews (НЕ каталог)

```text
GET …/kbbresearch/consumer-reviews/vehicleId/483508?perPage=…&sort=3&includeAiSummary=true
vehicleId: 483508  ← KBB id, не listingId
Role: отзывы — НЕТ для ingest
```

**ID на одной VDP (не путать):**

| ID | Пример | Назначение |
|----|--------|------------|
| `listingId` | 789850281 | объявление → `autotrader-789850281` |
| LSC model id | 487332 | `/rest/lsc/modelinfo/{id}` |
| KBB vehicleId | 483508 | отзывы |

### 8) cwa — visitor / analytics (НЕ каталог)

```text
Site: autotrader
When: VDP listing 789850281
Method: POST
URL: https://www.autotrader.com/cars-for-sale/cwa
Body: { "visitorId": "<pxa_id / abc>" }
Response: application/json ~632 B (br) — session/visitor config, не listing
Role: CWA = consumer web analytics / visitor state — НЕТ для ingest
```

### 9) payments — калькулятор + snapshot лота в query (ДА)

```text
Site: autotrader
When: VDP 789850281
Method: GET
URL: https://www.autotrader.com/rest/retailing/payments
  ?dealerZip=02601
  &mileage=3
  &vin=5NMP5DG1XVH150467
  &certifiedUsed=false
  &listingType=New
  &fueltype=Hybrid
  &styleId=487332          ← = modelinfo id
  &trim=Calligraphy
  &bodyType=Sport+Utility
  &transmission=Automatic
  &msrp=53285
  &salePrice=53285
  &dealerDiscountedPrice=53285
  &dealerId=100025532
  &zip=02645
  &partnerId=AMK
  &… (lease/loan terms)
Headers: accept: application/json, x-fwd-svc: atc
Role: payment quotes в Response; в QUERY уже vin/price/mileage/trim/type
     Для ingest полезен как подтверждение полей; не полный media/title
```

Маппинг из query (пример лота):

| Наше поле | Значение |
|-----------|----------|
| `car_id` | `autotrader-789850281` (из URL VDP, не из payments) |
| vin | `5NMP5DG1XVH150467` |
| price USD | `53285` (`salePrice` / `msrp`) |
| mileage | `3` |
| listing type | `New` |
| fuel / trans / body / trim | Hybrid / Automatic / Sport Utility / Calligraphy |
| dealerId | `100025532` |

### 10) `/rest/lsc/listing/similar` — похожие лоты (ДА, LSC list)

```text
Site: autotrader
Method: GET
URL: https://www.autotrader.com/rest/lsc/listing/similar
  ?dealerId=100025532
  &zip=null&searchRadius=100
  &excludedListingId=789850281
  &makeCode=HYUND&modelCode=SANTAFE
  &bodyStyleCode=SUV&extColorSimple=SILVER
  &transmissionCode=Automatic&listingType=NEW
  &startYear=2026&endYear=2028
  &numRecords=20
  &minPrice=50621&maxPrice=55949
  &channel=ATC
Headers:
  x-fwd-svc: atc
  x-coxauto-caller-id: CI2355308   ← caller id (не секрет API key, но фиксируем имя)
Role: JSON список похожих объявлений — ДА
      Namespace подтверждён: /rest/lsc/listing/…
Response item keys: TBD (Preview)
```

**Гипотеза:** есть sibling для одного лота, напр. `/rest/lsc/listing/{id}` или `/rest/lsc/listing/detail` — проверить фильтром `lsc/listing` на VDP/SRP.

### 11) getDealerInfo — дилер (ДА, location)

```text
Method: GET
URL: https://content.autotrader.com/content/dmd-main/dmdGearbox/getDealerInfo
  ?dealerId=100025532
Role: dealer name/address/phone — ДА для location
```

### 12) Doc VDP — `__NEXT_DATA__` = главный listing payload (ДА, разобран)

Файл пользователя: полный HTML VDP (~1.8 MB). Данные в:

```text
<script id="__NEXT_DATA__" type="application/json">
```

Путь к лоту:

```text
props.pageProps.__eggsState.inventory["789850281"]
```

Также: `pageProps.images` (дубль галереи), `pageProps.pageType = "vdp"`, `buildId` (пример: `KZwXc8oktCo_UL3kmiK10`).

Локальный sample (gitignored): `docs/research/usa-samples/autotrader-vdp-789850281-next-data.json`

#### pageProps keys

`currentUrl`, `images`, `query`, `dataIsland`, `pageType`, `__eggsState`

#### inventory[listingId] — поля для RideAuto

| Поле у нас | Autotrader path | Пример |
|------------|-----------------|--------|
| `car_id` | `id` | `autotrader-789850281` |
| title | `listingTitle` | New 2027 Hyundai Santa Fe Calligraphy |
| year | `year` | 2027 |
| make | `make.name` / `makeCode` | Hyundai / HYUND |
| model | `model.name` / `modelCode` | Santa Fe / SANTAFE |
| trim | `trim.name` / `atTrim` | Calligraphy |
| price USD | `pricingDetail.salePrice` (или `displayPrice` с fees) | 53285 / 54069 |
| vin | `vin` | 5NMP5DG1XVH150467 |
| mileage | `mileage.value` | 3 |
| listing status/type | `listingType` | New |
| fuel / drive / trans | `fuelType.name`, `driveType`, `transmission` | Hybrid… / AWD / Automatic |
| body | `bodyStyleCodes[]` | SUV |
| color | `color` / `exteriorColorSimple` | SILVER |
| stock | `stockNumber` | 38N00189 |
| styleId | `styleId` | 487332 (= modelinfo) |
| images[] | `images.sources[].src` | images.autotrader.com/hn/c/… (19 шт.) |
| dealer | `owner.id` / `ownerName` | 100025532 / Balise Hyundai… |
| location | `owner.location.address` | Hyannis, MA 02601 |

Другие полезные ключи listing (107 всего): `features`, `specifications`, `daysOnSite`, `kbbVehicleId`, `mpgCity`/`mpgHighway`, `pricingHistory`, `fullDescription`, `engine`, …

#### Ingest strategy (черновик)

1. **List:** `GET /cars-for-sale/all-cars?page={n}` → `__eggsState.srp_results` + `inventory`.
2. **Detail (опционально):** `GET /cars-for-sale/vehicle/{listingId}` → `inventory[listingId]` (полная галерея).
3. Дополнения: `/rest/lsc/listing/similar`, `/rest/lsc/modelinfo/{styleId}`, payments — не обязательны для MVP.

---

## Статус сбора

**VDP + SRP контракт достаточны для MVP-клиента.**  
Опционально дальше: фильтр make/year URL, page=2 sample, REST-альтернатива без HTML (если найдётся).

Cookies values не нужны.

---

## Архив: IAAI (закрыто — не API)

Только для истории; **не план реализации**.

- `POST https://www.iaai.com/Search?c=<unix_ms>` → HTML + cookies `vehicleItemIds`, `resultCount`
- Body: `Searches[]` (Facets / LongRanges), `PageSize`, `CurrentPage`, `Sort`, Sale/Bid filters
- Detail: XHR без vehicle payload; данные в Document HTML
- Copart: не разбирался
