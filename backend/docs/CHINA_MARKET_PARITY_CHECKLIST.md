# China (Che168) — паритет с контуром Encar / операционный чеклист

Внутренняя страница: что должно быть включено для «того же класса» продукта, что и Корея.

## Ингест и данные

- [ ] `che168_scraper.yaml` → DSN, proxy/Playwright, `store_raw_responses` при необходимости отладки.
- [ ] После прогона: **`postgres_catalog_sync`** (уже вызывается из `che168_scraper`, если не `SKIP_FRONTEND_EXPORT`).
- [ ] Повторный разбор из сырья: `python backend/scripts/reprocess_from_raw_envelope.py --source che168 --config …` (нужен сохранённый `cars.raw`).

## Ценообразование

- Формула: таможня РФ физлица + брокер + **доставка/документы в Китае 13 500 ¥** (в ₽ по курсу ЦБ) + **комиссия ВТБ 2 %** от стоимости авто в ₽ + **наши комиссии** (как у Кореи, `commission_car_tiers`).
- Версия правил в JSON: `pricing_clean.pricing_rules_version` = **`CHINA_PRICING_RULES_VERSION`** (`pricechina.py`). При bump — массовый синк или `repair_china_pricing_recompute_queue.py`.
- Эвристика очереди: `python backend/scripts/repair_china_pricing_recompute_queue.py --config che168_scraper.yaml` (dry-run / `--apply`).

## Качество и аудит

- Ночной аудит: `python backend/scripts/che168_parser_audit.py` (пороги, `--history-file`, Slack).
- Общие утилиты истории/печати: `backend/parser_audit_common.py` (и Encar, и China).
- Глубина сырья / envelope: `python backend/scripts/che168_raw_envelope_audit.py --config che168_scraper.yaml`.
- «Справочники» без отдельного hp_catalog: покрытие полей парсера — `python backend/scripts/che168_parser_field_coverage.py --config che168_scraper.yaml`.
- Кластеризация/dedupe: согласованность реестра — `python backend/scripts/che168_cluster_consistency_audit.py --config che168_scraper.yaml` (exit 1 при расхождении с правилом канона).

## Таксономия серий

- В `che168_scraper.yaml`: при пустом `series_api_path` прогон дерева вызывает `discover_che168_series_api_path` (кандидаты в `series_api_path_candidates`, опционально `series_probe_brandid`).
- Ручная проверка эндпоинта: smoke `backend/scripts/che168_smoke_fetch.py` при необходимости.

## Live «sold»

- `python backend/scripts/che168_listing_live_checker.py --config che168_scraper.yaml --once`
- Метрики: `CHE168_LIVE_CHECKER_PROMETHEUS_TEXTFILE` или `listing_live_checker.prometheus_textfile_path`.

## Slack

- Уведомления аудита: webhook или bot (`slack_ops.notify_slack_alert`).
- Корейский канал команды: `https://rideauto.slack.com/archives/C0B1XUQ8849` — задайте `OPS_SLACK_CHANNEL_ID` / webhook для ночных отчётов (China может использовать те же переменные или отдельный `CHE168_PARSER_AUDIT_SLACK_WEBHOOK`).

## Live-сверка цены (операционно)

- Бизнес-логика по умолчанию — цена из объявления; при необходимости сверки с API: `python backend/scripts/che168_price_drift_worker.py --config che168_scraper.yaml` (нужны DSN и рабочий `CHE168_DEVICE_ID` / session). В CI — только по явному флагу workflow (см. ниже).

## CI (опционально)

- Workflow **China catalog maintenance**: `.github/workflows/china_catalog_maintenance.yml` — `workflow_dispatch` и еженедельный cron; нужны секреты `DATABASE_URL` и при опциональных шагах `CHE168_DEVICE_ID`.
