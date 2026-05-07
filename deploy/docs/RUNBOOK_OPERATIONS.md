# Операционный контур: аудит, Meilisearch, откаты

Краткие шаги для продакшена (RideAuto). Детали переменных см. `deploy/env.rideauto.example` и скрипты в `deploy/scripts/`.

## 1. Nightly audit + price-intent case-check

- **Таймер**: `deploy/systemd/rideauto-encar-parser-audit.timer` → сервис вызывает `deploy/scripts/run_encar_parser_audit_nightly.sh`.
- **Что делает**: SQL-аудит Encar в Postgres (`backend/scripts/encar_parser_audit.py`), затем проверка зафиксированных кейсов (`backend/scripts/encar_price_intent_case_check.py`), если есть файл кейсов.
- **История**: JSONL по умолчанию `backend/data/encar_parser_audit_history.jsonl`; параметр `--keep-history-days` (в скрипте — `PARSER_AUDIT_KEEP_HISTORY_DAYS`, по умолчанию 7) обрезает файл до последних N дней по полю `ts`.
- **Пороги**: через env в `run_encar_parser_audit_nightly.sh` (`PARSER_AUDIT_MAX_MISSING_REQUIRED_PCT`, `PARSER_AUDIT_MIN_SCHEMA_COVERAGE_PCT`, и т.д.). Нулевая или отрицательная граница в коде аудита отключает соответствующий порог.
- **Алерты** (рекомендуется **Slack-приложение**):
  1. **Slack app + Web API** (основной вариант, уведомления приходят в канал в клиенте Slack / на устройстве, как у обычного бота):
     - В [api.slack.com/apps](https://api.slack.com/apps) создайте приложение, добавьте scope **chat:write** (и при необходимости **chat:write.public** для публичных каналов без предварительного приглашения бота), установите в workspace.
     - Скопируйте **Bot User OAuth Token** (`xoxb-…`) в `PARSER_AUDIT_SLACK_BOT_TOKEN` (или `OPS_SLACK_BOT_TOKEN`).
     - **Channel ID** целевого канала: в Slack → канал → About / сведения — скопируйте `C…` / `G…` в `PARSER_AUDIT_SLACK_CHANNEL_ID` (или `OPS_SLACK_CHANNEL_ID`). Бота нужно **добавить в этот канал** (`/invite @YourBot`), иначе `not_in_channel`.
  2. **Incoming Webhook** — альтернатива без OAuth: `PARSER_AUDIT_SLACK_WEBHOOK` (одна привязка к каналу).
  Порядок в коде: сначала пробуется токен бота + channel id, иначе webhook. Уведомление не отправится, если не задан ни один из этих способов (ошибка будет только в логе).
  - **Метка в тексте** (только для читаемости, не ID): `PARSER_AUDIT_SLACK_CHANNEL` — подставляется в человекочитаемый отчёт аудита в Slack.

После правки `/etc/default/rideauto`: `sudo systemctl daemon-reload` при необходимости и проверка `sudo systemctl start rideauto-encar-parser-audit.service`.

## 2. Синхронизация каталога Postgres → Meilisearch

- **С хоста**: `deploy/scripts/run_meilisearch_sync_host.sh` (ожидается `SYNC_PG_DSN` / `DATABASE_URL`, `WRA_MEILISEARCH_URL`, при необходимости `MEILI_MASTER_KEY`).
- **Из контейнера api**: `postgres_catalog_sync` после импорта может дернуть `infrastructure/meilisearch/sync_meilisearch.py`, если задан `WRA_MEILISEARCH_URL` и не выставлен `SKIP_MEILISEARCH_SYNC`.

### Preflight (блок «не устраивать вечное отключение»)

- По умолчанию включается через `WRA_MEILI_PREFLIGHT_GATE=true` в окружении, который наследует вызов sync (или флаг `--preflight-gate`).
- Проверка БД: `backend/scripts/meili_sync_preflight.py` — доля строк Encar с ценой / маркой / моделью не ниже порогов (`--preflight-min-*-pct` в `sync_meilisearch.py`, по умолчанию 97 / 99 / 99).
- **Если preflight не прошёл**: процесс завершается с кодом **2**, документы в индекс **не** отправляются — боевой индекс не «перезатирается» пустой синхронизацией.
- Если нужно временно ослабить или отключить только для одной команды: `WRA_MEILI_PREFLIGHT_GATE=false` для этого запуска или осознанно снизить пороги (см. также `backend/docs/PRICING_PIPELINE.md`).

## 3. Безопасная публикация индекса (второй UID + swap)

Цель: собрать данные в **staging UID**, затем атомарно поменять местами с **боевым UID**, который читает API (`WRA_MEILISEARCH_INDEX` в приложении, обычно `cars`).

1. На сервере синка задайте:
   - `WRA_MEILISEARCH_INDEX=cars_build` (или другой staging UID),
   - `WRA_MEILI_LIVE_INDEX=cars`,
   - `WRA_MEILI_SWAP_INTO_LIVE=1`.
2. Полная перезаливка staging (типичный ночной сценарий):

   ```bash
   WRA_MEILI_RECREATE_INDEX_ON_SYNC=1 bash deploy/scripts/run_meilisearch_sync_host.sh --recreate-index
   ```

   (или эквивалент через переменные из `/etc/default/rideauto`).

3. Скрипт вызывает `sync_meilisearch.py --swap-into-live`: после успешной загрузки документов выполняется Meilisearch **swap indexes** между live и build UID.

Если preflight падает на шаге до записи — staging и live не подменяются содержимым нового прогона.

**Не использовать swap** для инкрементальных обновлений «куска» данных без полной согласованной перезаливки staging — для инкремента оставляйте прямую запись в боевой UID без `--swap-into-live`.

## 4. Откат и переиндексация

| Ситуация | Действие |
|----------|----------|
| Последний swap оказался плохим, старые документы лежат во втором UID | Повторить **swap** между теми же двумя UID (ещё раз поменять местами содержимое `cars` и `cars_build`). |
| Индекс повреждён / нужен чистый полный rebuild боевого UID | Выключить swap; `--recreate-index` и `--index-name cars` при подтверждённом preflight; либо пересобрать staging и снова swap. |
| Preflight блокирует синк | Разобрать качество данных в Postgres (цены/бренды), либо временно ослабить пороги осознанно. |
| Нужно только применить settings JSON | `sync_meilisearch.py --settings-only` (без `--swap-into-live`). |

## 5. Связанные unit-файлы

- Meilisearch nightly: `deploy/systemd/rideauto-meilisearch-sync.service` + `rideauto-meilisearch-sync.timer`.
- Encar audit: `rideauto-encar-parser-audit.service` + `.timer`.

Проверка таймеров: `systemctl list-timers 'rideauto-*'`.

## 6. Che168 alert triage (Slack, без Telegram)

Ниже — быстрый чеклист под алерты из `deploy/prometheus/alert_rules_rideauto.yml`:

- **RideautoChe168HttpErrorsHigh**
  - Проверить health API Che168 из хоста: `curl -sS 'https://globalapi.che168.com/api/v1/brand?_appid=global.m&deviceid=<id>&language=en' | head -c 300`
  - Проверить прокси/egress (если используется): доступность URL и факт, что sticky IP не сменился.
  - Проверить последние логи `che168_scraper` по `status 403/429/5xx`.

- **RideautoChe168CircuitBreakerActive**
  - Это признак серии ошибок; сначала проверить `sessionid` и bootstrap.
  - Запустить быстрый smoke: `python backend/scripts/che168_smoke_fetch.py --config che168_scraper.yaml --limit 2 --detail-html --bootstrap`.
  - Если smoke падает, временно снизить конкуренцию (`http.concurrency`) и проверить proxy route.

- **RideautoChe168DetailFailSpike**
  - Проверить долю `detail_fail` vs `processed` в логах прогона.
  - Проверить, что `che168.fetch_detail_gallery_html` не упирается в бан detail page.
  - Проверить `CHE168_DEVICE_ID`, cookie/session freshness и ошибки `session refresh`.

Эскалация:
- Если алерт держится >30 минут и smoke не проходит — приостановить массовый прогон Che168, оставить только smoke/diagnostics и зафиксировать артефакты (логи + output JSON).

## 7. Encar alert triage (Slack, без Telegram)

Ниже — быстрый чеклист под алерты из `deploy/prometheus/alert_rules_rideauto.yml`:

- **RideautoEncarHttpErrorsHigh**
  - Проверить доступность Encar API из хоста:
    - `curl -sS 'https://api.encar.com/search/car/list/general?count=true&q=(And.Hidden.N._.CarType.N.)&sr=%7CModifiedDate%7C0%7C1' | head -c 300`
  - Проверить прокси-пул (если используется): `ENCAR_PROXY_URLS`, факт ротации egress и ошибки `407/429/5xx` в логах.
  - Проверить итоговые HTTP-метрики последнего прогона (`encar_http_*`) и корреляцию с `detail_fail`.

- **RideautoEncarCircuitBreakerActive**
  - Признак серийных сетевых/API ошибок — сначала проверить доступность прокси и стабильность upstream.
  - Запустить быстрый smoke:
    - `python backend/scripts/encar_smoke_fetch.py --config scraper_config.smoke.yaml --limit 2`
  - Если smoke падает: временно снизить `http.concurrency`, проверить `retry.*`/proxy route и запустить smoke повторно.

- **RideautoEncarDetailFailSpike**
  - Проверить долю `detail_fail` vs `processed` и статусы endpoint-ов (`endpoint_*_fail`) в логах `encar_scraper`.
  - Проверить таймауты (`detail_wall_timeout_sec`, `detail_extras_wall_timeout_sec`) и что нет массового `hard_deadline`.
  - Проверить, что fallback-парсинг фото работает (в smoke у `status=ok` есть `image_count > 0`).

Эскалация:
- Если алерт держится >30 минут и smoke не проходит — приостановить массовый прогон Encar, оставить только smoke/diagnostics и зафиксировать артефакты (логи + output JSON).
