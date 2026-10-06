# USA auctions — сбор эндпоинтов (IAAI / Copart)

Цель: зафиксировать **реальные** URL + форму ответов из браузера, прежде чем писать клиент/скрапер.  
Свитчер рынков на фронте **не трогаем** до отдельного решения.

## С чего начать (порядок)

1. **Сначала один сайт — IAAI** (`iaai.com`), потом Copart. Два сразу = путаница контрактов.
2. Обычный Chrome/Edge, обычный аккаунт если нужен login для списка.
3. DevTools → **Network** → фильтр `Fetch/XHR` (иногда ещё `Doc`).
4. Пройти сценарии ниже и для **каждого** интересного запроса сохранить строку в таблицу.

Антибот (Incapsula/Cloudflare и т.п.) — норма. Нас интересует, **какой JSON** видит уже прошедший браузер, не «как обойти капчу в коде».

## Сценарии (чеклист)

Отмечай `[x]` когда снял хотя бы один пример ответа (HAR / Copy → Copy as cURL / JSON в файл).

### A. Список / поиск

- [ ] Открыть поиск / inventory (used / salvage list)
- [ ] Сменить страницу (page 2)
- [ ] Применить 1–2 фильтра (make, year, location)
- [ ] Записать: method, URL (без секретов), query/body, ключевые поля item

### B. Карточка лота

- [ ] Открыть один лот из списка
- [ ] Записать id лота (stock/lot/item number)
- [ ] Галерея фото (отдельный запрос или внутри detail?)
- [ ] Цена / статус аукциона / локация / VIN если есть

### C. Служебное

- [ ] Есть ли отдельные `brands` / `facets` / `locations` API?
- [ ] Что в Cookies после прохождения challenge (только **имена**, не значения в git)
- [ ] Нужен ли login для публичного списка

## Шаблон записи (копируй блок на каждый эндпоинт)

```text
### <короткое имя, напр. search_page>
Site: iaai | copart
When: <сценарий A/B>
Method: GET|POST
URL: https://...
Auth/cookies needed: yes/no (имена cookie, не значения)
Request notes: query/body keys only
Response shape (top-level keys):
Item id field:
Title / year / make / model fields:
Price / bid / buy-now fields:
Status / sale date / location:
Images:
Sample saved as: docs/research/usa-samples/<file>.json  (gitignored if bulky)
```

## Куда класть сырьё

- Этот файл — контракт-черновик (в git).
- Тяжёлые JSON/HAR: `docs/research/usa-samples/` (локально; см. `.gitignore`).
- **Не коммитить** session cookies, токены, полные HAR с Authorization.

## Целевой контракт RideAuto (после сбора)

| Поле у нас | Откуда с аукциона (заполнить) |
|------------|-------------------------------|
| `source` | `iaai` / `copart` |
| `car_id` | `<source>-<lot_id>` |
| title / year / make / model | |
| price (USD?) | |
| vin | |
| images[] | |
| listing status (sold/upcoming) | |
| location | |

## Найденные эндпоинты

### IAAI

_(пока пусто — заполняем вместе по мере съёма)_

### Copart

_(после IAAI)_

## Решение по продукту (зафиксировано)

- Рыночный **свитчер** Корея/Китай пока без изменений.
- США — отдельный `market`/`source`, не «все в одной ленте» на старте.
