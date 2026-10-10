# Catalog Pipeline Platform

Единый оркестратор: **Postgres prices → Meilisearch** без опустошения live-индекса.

## Запуск

```bash
# Полный пайплайн (хост /opt/rideauto)
sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_catalog_pipeline_host.sh

# Systemd
sudo systemctl enable --now rideauto-catalog-pipeline.timer
sudo systemctl start rideauto-catalog-pipeline.service
```

Скрипты стадий: [`run_postgres_catalog_sync_host.sh`](../scripts/run_postgres_catalog_sync_host.sh), [`run_meilisearch_sync_host.sh`](../scripts/run_meilisearch_sync_host.sh), оркестратор [`run_catalog_pipeline_host.sh`](../scripts/run_catalog_pipeline_host.sh).

## Blue/green (обязательно при recreate)

В `/etc/default/rideauto`:

```bash
WRA_MEILISEARCH_INDEX=cars_build
WRA_MEILI_LIVE_INDEX=cars
WRA_MEILI_SWAP_INTO_LIVE=1
WRA_MEILI_PREFLIGHT_GATE=true
```

`sync_meilisearch.py` **отказывает** `--recreate-index` на live UID без `--swap-into-live` (fail-closed).

## Ресурсные лимиты (OOM-защита)

`postgres_catalog_sync` держит весь каталог в RAM (дедуп) — при ~158k машин это ~14 ГБ.
На хосте 16 ГБ RAM + 8 ГБ swap, поэтому пайплайн **обязан** жить в ограниченном cgroup:

| Кто запускает | Как ограничен |
|---|---|
| `rideauto-catalog-pipeline.service` (timer 03:30) | `MemoryHigh=10G`, `MemoryMax=12G` |
| супервизор скраперов (финальный sync) | отдельный `systemd-run --scope --property=MemoryMax=12G` (`WRA_SUPERVISOR_CATALOG_MEM_MAX`) |
| дневные `rideauto-*-auto-update.service` | свой sync не гоняют вообще (`Environment=SKIP_POSTGRES_CATALOG_SYNC=1` / `SKIP_FRONTEND_EXPORT=1`) |

ADR 0004: каталог синхронизирует **только** catalog-pipeline (timer) — дневные апдейты
не должны поднимать 14-ГБ sync внутри своего юнита.

`rideauto-scraper-supervisor.service` дополнительно имеет `MemoryMax=8G` + `OOMPolicy=continue`:
OOM внутри его cgroup убивает только виновника (скрапер), а не останавливает юнит
(раньше OOM-килл в этом cgroup давал десятки рестартов `Restart=always`).

См. также [`SCALE.md`](./SCALE.md) (ADR 0004) и [`RELEASE_CHECKLIST_CATALOG.md`](../../backend/docs/RELEASE_CHECKLIST_CATALOG.md) §0.

## Скорость KR-докачки (Encar): прокси, конкурентность, тормоз discovery

Прод-базлайн (2026-10-10): пул живых KR-прокси в `ENCAR_PROXY_URLS` (`/etc/default/rideauto`),
`SCRAPER_HTTP_CONCURRENCY`, `SCRAPER_HTTP_CONN_LIMIT_PER_HOST`, `ENCAR_PROMETHEUS_TEXTFILE`, плюс
тормоз discovery в `scraper_config.yaml` и `http.transport_max_clients` (см. диагноз ниже).

| Рычаг | Где | Смысл |
|---|---|---|
| `ENCAR_PROXY_URLS` | `/etc/default/rideauto` | Пул KR-прокси (`http://user:pass@host:port`, через запятую). Пул `×N` → примерно линейный рост detail-разбора до потолка Encar/провайдера. |
| `SCRAPER_HTTP_CONCURRENCY` (env) / `http.concurrency` (yaml) | env / `scraper_config.yaml` | Параллельные detail-воркеры. Держать ≤ размеру пула (например 22 прокси → 24). |
| `http.fetch_detail_extras` | `scraper_config.yaml` | `true` = полный лот (detail + record/diagnosis/inspection/sellingpoint/user). `false` = быстрый «каркас» (≈ ×3 меньше запросов на авто) — **второго прохода в коде нет**, включать только с планом backfill. |
| `http.list_pause_when_pending_above` | `scraper_config.yaml` | Пока `scraper_pending_ids(scope=encar)` ≥ порога, list-фаза спит 20 с (+jitter 0–3 с), лог раз в 5 мин: discovery не забивает очередь быстрее, чем detail её ест. Требует патча `workers.py` (`pause_pending_above`) — до 2026-10-10 он не был задеплоен, поэтому порог 30000 не срабатывал вообще. |
| `http.list_max_parallel` | `scraper_config.yaml` | Сколько срезов `list_q_suffixes` крутится одновременно. Меньше — меньше запросов к list API (полезно, когда очередь уже большая). |
| `http.transport_max_clients` | `scraper_config.yaml` | Потолок «в полёте» для curl_cffi-сессии: `AsyncSession(max_clients=…)`. **Обязательный к проверке рычаг**: у curl_cffi дефолт `max_clients=10`, а сессия одна на все detail-воркеры, поэтому `http.concurrency > 10` не даёт прироста вообще. `0`/пусто = авто `max(32, concurrency, conn_limit_per_host) * 2`. |
| `http.fetch_user_extras` | `scraper_config.yaml` | `GET /user/{Separation[0]}` — **404 в 491/491 карточек** (проверено по `cars.data->'_raw'->'source_meta'`), т.е. чистый мусор. С 2026-10-10 по умолчанию `false`; замер по `encar.prom` до/после: **запросов на авто 6.07 → 5.07**, `encar_http_final_http_errors_total` на авто **2.36 → 1.46** (выпавший ≈1.0 на авто — это `user`; остаток — легитимные 404 у `diagnosis`/`inspection`/`record`). Темп не изменился (extras идут `gather`, время карточки задаёт самый медленный), выигрыш — меньше нагрузки на прокси и меньше ложного шума в метрике. |
| `http.detail_zero_fail_backoff_base_sec` / `..._max_sec` | `scraper_config.yaml` + `workers.py` | Джиттер-пауза воркера (1 → 15 с), когда `detail` вернулся **без HTTP-кода** (`status=0`: мёртвый прокси / открытый CB). Без неё окно CB 90 с выжигало 450–650 карточек: воркеры крутили `pop → fail → requeue` без пауз. `base=0` = выключить. |
| `http.timeout_total` / `timeout_connect` / `timeout_sock_read` | `scraper_config.yaml` | Транспортный потолок curl_cffi = `max(total, sock_read + connect)`. Прод-факт: при 30/10/25 мёртвый прокси держал слот **35 с** (`curl: (28) Connection timed out after 35000 ms`) — именно этот таймаут копил серию отказов до открытия CB. С 2026-10-10: 24/8/16 → потолок 24 с. |

**Как менять безопасно (в порядке операций).**

1. Обновить `ENCAR_PROXY_URLS` в `/etc/default/rideauto` (бэкап: `cp -a` в `/root/`).
2. Править `http.*` в `/opt/rideauto/scraper_config.yaml` (или через `SCRAPER_HTTP_*`).
3. Убить **только** encar-ребёнка: супервизор поднимет его сам и передаст новое окружение —
   `start_as_rideauto()` в `rideauto_scraper_supervisor.py` выполняет
   `set -a; . /etc/default/rideauto; . /opt/rideauto/.env; set +a` перед запуском.
   Рестарт супервизора **не нужен** (и нежелателен: он убил бы все рынки сразу).
4. Очередь не теряется: `pending` живёт в `scraper_pending_ids`, при старте лог пишет `Resumed pending: N`.
   Ребёнок после `kill -TERM` поднимается **на следующем тике супервизора** (`WRA_SUPERVISOR_INTERVAL_SEC=120`),
   т.е. простой до ≈2–2.5 мин. Новый прогон пишет новый `logs/overnight/encar_sup_<utc-stamp>.log`.
   Готовый помощник деплоя (бэкап → `cat` → sha256 → `py_compile` → kill → проверка лога):
   `py -3.14 -X utf8 var/_de4_deploy_backoff.py`.

> Осторожно с `pkill -f`: скрипт, который сам содержит строку `/opt/rideauto/backend/encar_scraper.py`
> в тексте, матчится своим же `pkill -f '…encar_scraper.py'` и убивает себя. Используйте поиск PID
> через `pgrep` и исключение `$$`, либо паттерн без полного пути.

**Второй проход по extras (если включали `fetch_detail_extras: false`).** Enqueue в
`encar_scraper.py` берёт строки только из `scraper_pending_ids` (без проверки `is_collected`),
поэтому backfill делается SQL-вставкой id в `scraper_pending_ids(scope='encar')` — скрапер доберёт их
как обычные pending, уже с включёнными extras.

См. также [`SCALE.md`](./SCALE.md) и раздел «Ресурсные лимиты (OOM-защита)» выше.

### Диагноз 2026-10-10: «22 прокси не ускорили Encar»

Наблюдение: пул прокси увеличен с 4 до 22 (conc 24), а темп не вырос и даже падал
(≈136 авто/мин против ≈168 авто/мин на 4 прокси).

Замеры на прод-хосте, **одинаковая нагрузка** (48 detail-запросов, conc=24, те же 22 KR-прокси):

| Конфигурация `AsyncSession(...)` | req/s |
|---|---|
| без аргументов (дефолт `max_clients=10`) | **2.24** |
| `max_clients=64` | **17.13** |
| `max_clients=128` | 18.78 |

Вывод: узкое место — не пул прокси, а потолок `max_clients=10` у `AsyncEncarClient`
(один `AsyncHttpTransport`/`AsyncSession` на все воркеры). Пока он не поднят, и `concurrency`,
и размер пула прокси влияют примерно никак. Подтверждение в `Transport[encar]: curl_cffi
impersonate=… max_clients=…` при старте; gauge `scraper_transport_max_clients{source="encar"}`
(если 0 или 10 — фикс не доехал).

Сопутствующие факты (не менять пул вслепую):

* 10–30 % detail-запросов падают с `status=0` (transport-level: таймаут 15 c / обрыв) —
  одинаково при 4 и 22 прокси, т.е. это цена связки прокси↔Encar, а не перегрузка IQ.
* Проверка кредов пула: у ~5 из 22 «живых» прокси на момент замера не работала одна из ног
  (вход или выход), они просто тратят 15 c таймаута на каждый запрос.
* «407/429/403/404» в логах ошибок — ложные срабатывания парсера (числа вытаскивались из
  `car_id`), реальные отказы — только `status=0`.
* CPU хоста 5.6 % — не GIL и не CPU-боттлнек.

Отдельная известная проблема (не эта правка): на холодном старте list-фаза гасла целиком —
все 32 среза падали на `offset=0` с `status=0 err=circuit_breaker_open` (общий CB залипал
после стартового шторма `status=0`). Кандидаты: отдельный CB для list-фазы или ретрай list
после закрытия CB. До этого discovery прирастал только через `list_q_suffixes`-срезы,
успевшие пройти до залипания.

### Прод-результат 2026-10-10 (`transport_max_clients: 64`)

Задеплоено на DE-4 (бэкапы: `/root/maxclients-*`, `/root/workers-pause-*`, `/root/encar-scraper-prom-*`):

| Метрика (окно 2–3 мин, один и тот же пул 22 KR-прокси) | До | После |
|---|---|---|
| `processed` (авто/мин) | ≈136 (падало до 38 при залипшем `circuit_breaker`) | **354–375** |
| `http_ok` (req/s) | ≈5.4 | **20.9–23.8** |
| `detail_fail` / `cb_short` | до 183 870 | **0 / 0** |
| `pending` (динамика) | +280…+630 в минуту (discovery быстрее detail) | **−200…−400 в минуту** |

Проверка на проде:

```bash
L=$(ls -t /opt/rideauto/logs/overnight/encar_sup_*.log | head -1)
grep 'Transport\[encar\]: curl_cffi' "$L"      # → … max_clients=64 (conn_limit_per_host=24)
grep -c 'List pause' "$L"                      # → 32 (все срезы ждут разбор pending)
grep 'Stats:' "$L" | tail -3
```

Что ещё вошло в этот деплой:

* `http.transport_max_clients: 64` (`scraper_config.yaml`, env-аналог `SCRAPER_HTTP_TRANSPORT_MAX_CLIENTS`);
  `0`/пусто → авто `max(32, concurrency, conn_limit_per_host) * 2`.
* `workers.py`: пауза discovery по `pending` (см. рычаг выше) + гейт `http.fetch_detail_extras` (в проде `true`).
* `encar_scraper.py`: `*.prom` переписывается каждые 60 с, а не только на выходе прогона — иначе длящийся
  сутки прогон вообще не виден в дашбордах.

### Метрики (node_exporter textfile)

| Metric | Meaning |
|--------|---------|
| `wra_job_last_*{job="wra_catalog_pipeline"}` | Оркестратор |
| `wra_job_last_*{job="wra_postgres_catalog_sync"}` | Стадия PG |
| `wra_job_last_*{job="wra_meilisearch_sync"}` | Стадия Meili |
| `wra_catalog_pg_active_rows` | PG rows без dedupe link |
| `wra_catalog_meili_documents` | Live Meili docs |
| `wra_catalog_index_empty` | 1 если Meili пуст |
| `wra_catalog_meili_pg_ratio` | docs/rows |
| `scraper_transport_max_clients{source="encar"}` | Фактический `AsyncSession(max_clients=…)` — должен быть ≥ `http.concurrency` (дефолт curl_cffi 10 = темп режется) |
| `encar_scraper_processed_total`, `encar_scraper_saved_total`, `encar_scraper_list_pages_total` | Прогресс KR-докачки; обновляются раз в 60 с (`encar.prom`), а не только на exit прогона |

Файл метрик: env `ENCAR_PROMETHEUS_TEXTFILE` (прод: `/var/lib/node_exporter/textfile_collector/encar.prom`),
иначе корневой `prometheus_textfile_path` из `scraper_config.yaml`. Скрапер бежит под пользователем
`rideauto`, поэтому каталог textfile-коллектора на проде: `chgrp rideauto && chmod 2775`
(файлы получаются `rideauto:rideauto 644` — читаются экспортёром). На 2026-10-10 `node_exporter`
на хосте ещё не запущен (`systemctl is-active node_exporter` → `inactive`), метрика пишется файлом
и подхватится, когда экспортёр поднимут.

**Оговорка по `encar_http_final_http_errors_total`** (проверено 2026-10-10 по `cars.data->'_raw'->'source_meta'`,
500 карточек): в счётчик попадают 404 от **необязательных** extras-эндпоинтов — `user` 404 в 491/491 (100 %),
`diagnosis` 285/500, `inspection` 205/500, `record` 189/500, тогда как `detail` и `sellingpoint` всегда 200.
Итого ≈2.3 «ошибки» на авто при `detail_fail=0` и `cb_short=0`, т.е. правило
`RideautoEncarHighFinalHttpErrors` (порог 15 % от `requests_total`) будет срабатывать **ложно**.
Развитие: разделить счётчик на жёсткие ошибки и «optional extras», либо поднять порог.
Отдельный кандидат на разбор: `fetch_user` по `Separation[0]` всегда даёт 404 — это ≈1 бесполезный
запрос на карточку (≈16 % трафика).

Каталог lag: [`backend/scripts/catalog_pipeline_lag_metrics.py`](../../backend/scripts/catalog_pipeline_lag_metrics.py).

### Состояние обхода каталога Encar (2026-10-10, прод, проверено)

- Каталог по ответам list API: `for` (импорт) **64 790** + `kor` (внутренний) **130 550** ≈ **195 340**
  объявлений (поле `api_count` из строк `List car_type=… api_count=…`).
- В БД: `cars(source='encar')` **49 704**, `scraper_collected_ids(scope='encar')` **50 320**,
  `scraper_pending_ids` **35 218** → известно ~85.5k id, т.е. ~44 % каталога.
- `list_offset_for = 2 262 900`, `list_offset_kor = 2 253 400` при `api_count` 64 790 / 130 550: базовые
  срезы ушли далеко за «естественный» конец выдачи (Encar принимает большие offset, и на глубоких
  страницах всё ещё попадаются новые id, поэтому ни `List exhausted`, ни `List stall`/`stall jump`
  в логах 8 последних запусков не появлялись).
- **Срезы `list_q_suffixes` (починено 2026-10-10).** Все 15 брендовых срезов давали
  `List page failed … variant=kor_vN / for_vN offset=0 status=404` (404 не входит в `retry_statuses`
  → срез выходил сразу), т.е. discovery делала 2 запроса вместо 32. Причина: формат q-суффикса
  `_.(And.Manu.[현대].)` — сокращение `Manu` и квадратные скобки вокруг значения. Проверено на проде
  (`var/_de4_q_probe.py`): `_.Manufacturer.현대.` → **200, count=47744**;
  `_.(And.Manufacturer.현대.)` → 200/count=47744; `_.Manufacturer.[현대].` → 200, но **count=0**
  (скобки ломают матчинг молча — хуже 404). Плюс три «домашних» марки в справочнике Encar зовутся
  со старым именем в скобках: `KG모빌리티(쌍용)`, `르노코리아(삼성)`, `쉐보레(GM대우)`; а импортный
  бренд — `도요타`, не `토요타`. Итог (`var/_de4_brand_probe.py`, 2026-10-10): **40 срезов, все
  отвечают 200**; покрытие по `count` ≈ `for` 63 920/64 754 = **98.7 %**, `kor` 130 432/130 472 =
  **99.97 %**. Срезы с индексом 16+ дописаны в конец списка — ключ чекпоинта `"{car_type}_v{index}"`,
  поэтому вставка в середину сдвинула бы `offset` уже идущих срезов. Регресс-тест:
  `backend/tests/test_scraper_config_list_slices.py` (ловит возврат `[...]`/`Manu.` в конфиг).
- Вспышки `detail failed status=0` (transport-level, без HTTP-кода) — **разобраны 2026-10-10**.
  Причина по строке клиента:
  `Encar circuit breaker: open 90s after failures (status=0 err=Failed to perform, curl: (28)
  Connection timed out after 35000 milliseconds)` — т.е. висел прокси (или залипший коннект) до
  транспортного потолка 35 с (`max(timeout_total, sock_read + connect)`), набиралась серия 12 отказов
  (счётчик общий на клиента, `status=0` из exception-пути тоже считается) → CB открывался на 90 с →
  все 24 воркера получали `circuit_breaker_open` мгновенно и **без пауз** выжигали очередь:
  `pop → fail → requeue`. Отсюда `detail_fail`/`cb_short` росли синхронно (650/690 в 11:46–11:47,
  ещё +467/+502 в 12:00–12:01, `cb_open` = это **счётчик открытий**, а не gauge, поэтому «cb_open=3»
  не значит «CB всё ещё открыт»).
  Масштаб: до фикса `max_clients` за 10:11–10:59 было **99 411** таких строк (прокси/сессия деградировали
  в дефолтных 10 слотах), после фикса — эпизоды 11:46 и 12:00 (≈1 100–1 300 карточек, 1–2 минуты).
  Митигации, задеплоенные 12:10: потолок транспорта 35 → 24 с, `detail_zero_fail_backoff_*`
  (воркер спит 1→15 с при `status=0`), `fetch_user_extras: false`.
  Корневое лечение (сделано 2026-10-10): **health-quarantine прокси** — `ProxyPool` считает подряд
  идущие отказы URL (`failure_threshold`, включая `status=0`/407) и убирает его из ротации на
  `quarantine_sec`; успех сбрасывает серию. Пока живы другие URL, «мёртвый» не выбирается, а если
  закарантинены все — отдаётся тот, у кого карантин истекает раньше (без зависания на пуле).
  Наблюдаемость (все пять строк пишутся в `encar.prom`, экспортёр
  `scraper_pipeline/resilience/prometheus.py`): `scraper_proxy_urls_total`,
  `scraper_proxy_quarantined`, `scraper_proxy_quarantine_events_total`,
  `scraper_proxy_quarantine_skips_total`, `scraper_proxy_failures_total`.
  Тесты: `tests/test_common_proxy_backoff.py`, `tests/test_encar_proxy_quarantine.py`,
  `tests/test_encar_scraper_prometheus.py`. Выключено при `proxy.failure_threshold: 0`.
  Задеплоено и проверено на проде 2026-10-10 13:13 MSK: в новом процессе `grep -c 'List phase'`
  = **80** (2 типа × 40 срезов, `variant 1/40 … 40/40`, `checkpoint_key=<car_type>_vN`), за первые
  135 с `detail_fail=0 cb_open=0 cb_short=0 retries=0`, в `encar.prom` присутствуют все пять
  `scraper_proxy_*` (`proxy_urls_total=22`). Деплой — хирургический патч прод-конфига (только блок
  `list_q_suffixes` + два knob'а, остальное байт-в-байт) и SFTP трёх модулей через
  `var/_de4_deploy_slices_quarantine.py`; бэкап — `/root/encar-slices-quarantine-<ts>/`, рестарт
  encar делает сам супервизор (≤120 с).
- ETA полного дампа (оценка 2026-10-10 12:00): сделано ≈50 320 id, осталось ≈145 000;
  detail даёт 350–400 авто/мин → ≈6.5 ч чистой работы (≈19:00–20:00 MSK) плюс потери на эпизоды CB.
  Discovery замерен отдельно (лог 11:25–11:31, паузы не было): 393 страницы за 6.7 мин = 58 стр/мин,
  **548 новых id/мин** (кор. срез 13.6 id/стр, импорт 5.1 id/стр; 66 % страниц пустые) — то есть
  discovery быстрее detail, поэтому очередь и приходится паузить.

Служебные скрипты этой сессии (в `var/`, запуск `py -3.14 -X utf8 var/_de4_ssh_run_file.py <файл>`):
`_de4_full_state.sh` (coverage/offsets/pending), `_de4_discovery_probe.sh` (живые list-срезы),
`_de4_burst_probe.sh` (вспышки `status=0`), `_de4_meta_probe.sh` (extras-404 в `source_meta`),
`_de4_parity.py` (хэши local↔prod), `_de4_final_health.sh` (rate/mem/pause/prom).
Деплой фикса срезов/карантина: `var/_de4_deploy_slices_quarantine.py` (`--plan` — только чтение,
`--payload-only`, `--restart`, `--restart-only`), host-side патчер YAML
`var/_de4_patch_slices_quarantine.py` (с `--dry-run` и offline-смоуком `ProxyPool`),
`var/_de4_pull_prod_config.py` (снять прод-конфиг перед дельтой),
`var/_de4_post_deploy_verify.py` (процесс, boot-лог, `List phase`, `encar.prom`).
Каталог `var/` целиком в `.gitignore`: там прод-дампы с `ENCAR_PROXY_URLS` (логин:пароль).

## Прод-Done gate

1. Timer активен; last success < 26h.
2. `wra_catalog_meili_documents > 0`.
3. Preflight проходит или override задокументирован.
4. Алерт `RideautoCatalogIndexEmpty` не firing в норме.

См. также [`backend/docs/RELEASE_CHECKLIST_CATALOG.md`](../../backend/docs/RELEASE_CHECKLIST_CATALOG.md) §0.
