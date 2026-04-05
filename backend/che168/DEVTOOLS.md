# Che168: что снять в DevTools для парсера

Откройте **Chrome → F12 → Network**, включите **Preserve log**, фильтр **Fetch/XHR** (и при необходимости **Doc**).

## 1. Список объявлений

1. Зайдите на страницу листинга, например `https://www.che168.com/china/list/`.
2. Прокрутите список / смените страницу / примените фильтр в UI.
3. Запишите все запросы, после которых **обновляется сетка карточек** (не баннеры и не метрика).

Интересуют в первую очередь:

- **URL** (полный path + query).
- **Method** (GET/POST).
- **Request headers**: `Cookie`, `Referer`, `User-Agent`, кастомные заголовки (часто есть подпись или токен).
- Для POST: **тело** (JSON или form).
- **Response**: сохраните один успешный JSON как файл-пример (или скрин структуры в Preview).

Типичные паттерны у китайских автосайтов: `api`, `list`, `search`, `getcarlist`, `usedcar`, домены вроде `api.che168.com`, `apigateway`, `m.autohome.com.cn` — но ориентируйтесь на **фактическую сетку**, а не на название.

## 2. Карточка объявления

1. Откройте объявление вида `https://www.che168.com/dealer/{dealerId}/{offerId}.html`.
2. То же самое: какие **XHR** отдают **цену, VIN/номер, год, пробег, город, комплектацию, галерею**.

Дополнительно проверьте вкладку **Elements** на наличие:

- `<script id="__NEXT_DATA__" type="application/json">` (Next.js),
- встроенного `window.__INITIAL_STATE__` / похожих глобалов.

Если такое есть — скопируйте **сырой JSON** (он часто дублирует или заменяет XHR).

## 3. Пагинация и фильтры

Для каждого действия в UI зафиксируйте, **какой параметр в запросе меняется**:

- номер страницы, `page`, `pageindex`, `pageIndex`;
- регион/город;
- марка/модель (часто это **числовые id**, а не слаги из URL);
- сортировка.

## 4. Защита и лимиты

- Есть ли **429 / 403**, капча, редирект на логин.
- Повторяется ли запрос **без Cookie** (из `curl`) — если нет, в парсере нужны сохранённые cookie или обход нецелесообразен.

## 5. Что передать в репозиторий

Достаточно **одного набора** (можно в issue или личным сообщением):

1. HAR нескольких кликов (листинг + деталь) **или** экспорт «Copy as cURL» для 2–3 ключевых запросов.
2. Текстовый фрагмент JSON ответа списка (с **замаскированными** персональными данными, если есть).

После этого можно стабильно повторить запросы в `che168/client.py` / отдельном модуле и нормализовать поля под `data_json` как у Encar.

## 6. Разбор переданных HAR (главная каталога, фильтры, карточка)

По файлам `HAR главной каталога.har`, `Har диапазон года.har`, `Har выбор модели.har`, `www.che168.com.har`, `HAR карточка авто.har`:

### Листинг и фильтры

В этих дампах **нет отдельного XHR**, который возвращает JSON со списком машин. После действий в каталоге меняется **полный URL документа** и снова грузится **HTML** (`www.che168.com/china/...`), например:

- `/china/list/` — общий список;
- `/china/beiqixinnengyuan/` — после выбора модели (пример из HAR);
- `/china/beiqixinnengyuan/a3_5msdgscncgpi1ltocsp1ex/?pvareaid=100513` — после диапазона года/других фильтров (slug в path).

Параллельно дергаются вспомогательные API (их **не** использовать как источник списка объявлений):

| URL (фрагмент) | Назначение |
|----------------|------------|
| `apipcmusc.che168.com/v1/list/getaroundhotcities` | горячие города |
| `apipcmusc.che168.com/v1/pc/dealerad` | реклама |
| `apipcmusc.che168.com/v1/ip/getiplocation` | IP-гео |

**Вывод для парсера списка:** тянуть **страницу HTML** по итоговому URL фильтра и вытаскивать карточки (как сейчас в `parse.py` по ссылкам `/dealer/{dealer}/{infoid}.html`), либо искать в HTML встроенный JSON (если появится в других страницах).

### Карточка объявления (`HAR карточка авто.har`, пример `dealer/143430/57569738.html`)

Идентификатор объявления на API: **`infoid=57569738`** (совпадает с числом в URL). Плюс **`dealerid=143430`**, **`specid`**, **`seriesid`**, регион **`cid` / `pid`**, иногда **`mark`** (например `uahp10031`).

| Хост / путь | Параметры (важное) | Смысл |
|-------------|-------------------|--------|
| `apipcmusc.che168.com/v1/car/getusedcaroptiondata` | `infoid` | Список опций: `optionid`, `optionname`, `optionpics` (JSONP). |
| `yccacheapigo.che168.com/api/carinfo/getmaintenance` | `seriesid` | Обслуживание / график ТО. |
| `yccacheapigo.che168.com/api/carinfo/getheatrank` | `seriesid`, `infoid` | «Жара» / интерес к объявлению. |
| `yccacheapigo.che168.com/api/carinfo/getdealerdprank` | `dealerid` | Рейтинг дилера. |
| `yccacheapigo.che168.com/api/carinfo/getscorebyspecid` | `specid` | Оценка (Koubei). |
| `yccacheapigo.che168.com/api/carinfo/specprc` | `specid` | Ценовой блок Koubei. |
| `pinguapi.che168.com/v1/auto/autoassess.ashx` | `infoid`, `specid`, `mileage`, `firstregtime`, `mark`, `cid`, `pid` | Справочная оценка / «референсная цена». |
| `apiassess.che168.com/origin/quotescore` | `specid`, `mileage`, `firstregtime`, `price` | Оценка (в логах бывает **403**). |
| `apiassess.che168.com/api/NewCarPriceInTax.ashx` | `specid`, `cid` | Цена новой (**403** в том же HAR). |
| `apipcmusc.che168.com/v1/insurance/getcarbatteryreportdata` | `vincode` (обфусцированная строка) | Отчёт по батарее (EV). |
| `apicone.che168.com/config/protocalcheck` | `cid`, `seriesid` | Служебная проверка. |

Основные поля (цена, пробег, год в шапке) по-прежнему разумно брать из **HTML карточки** или из параметров, которые уже передаются в `autoassess` (там видны `mileage`, `firstregtime`, `specid`).
