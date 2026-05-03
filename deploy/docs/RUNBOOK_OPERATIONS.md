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
  Порядок в коде: сначала пробуется токен бота + channel id, иначе webhook. Если ни один канал Slack не настроен — запасной вариант **Telegram** (`OPS_TELEGRAM_BOT_TOKEN` + `OPS_TELEGRAM_CHAT_ID`).
  - **Метка в тексте** (только для читаемости, не ID): `PARSER_AUDIT_SLACK_CHANNEL` — подставляется в тело отчёта аудита.

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
