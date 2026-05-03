# Аудит внедрённых улучшений (данные, платформа, процесс)

Дата: 2026-05-03. Кратко: что сделано в коде/репозитории и что улучшить дальше.

## Реализовано

### Данные (Postgres + Meili)

| Компонент | Описание |
|-----------|----------|
| Миграция `008_catalog_dedupe_canonical.sql` | Колонка `cars.dedupe_canonical_car_id`, индексы |
| `fastapi_app/pg_catalog.py` | Разрешение цепочки дублей при `fetch_cars_by_ids` / `fetch_car_any_id` |
| `sync_meilisearch.py` | В выборку попадают только строки без `dedupe_canonical_car_id` |
| `catalog_dedupe.py` | `terminal_car_id_for_dedupe_map` для обхода цепочки |
| `scripts/catalog_dedupe_link.py` | CLI: связать дубликат с каноническим `car_id` |
| `search.py` | Slim использует `car["id"]` (канонический) после разрешения дедупа |

### Платформа

| Компонент | Описание |
|-----------|----------|
| OpenTelemetry | `fastapi_app/otel_tracing.py`, `WRA_OTEL_*`, OTLP HTTP |
| Rate limit | `slowapi`, `WRA_RATE_LIMIT_PUBLIC_PER_MINUTE`, опционально Redis |
| Метрики job | `scripts/prometheus_job_textfile.py` + переменные `JOB_NAME`, `EXIT_CODE`, `DURATION_SEC` |
| Бэкапы | `docs/BACKUP_RESTORE.md` (Postgres, Meili, Redis) |

### Процесс

| Компонент | Описание |
|-----------|----------|
| `.github/CODEOWNERS` | Владелец `@danyaleyman` (смените при переносе в org) |
| Batch-дедуп | `scripts/catalog_dedupe_suggest.py` — отчёт групп по `catalog_dedupe_key` |
| Prometheus alerts | `deploy/prometheus/alert_rules_rideauto.yml` |
| Job wrapper | `deploy/scripts/run_with_prometheus_job_metrics.sh` |
| `docs/adr/` | README + ADR 0001 про схему Meilisearch |

## Пробелы и предложения по улучшению

1. **Автоматическое обнаружение дублей** — отчёт: `catalog_dedupe_suggest.py`; связывание пар: `catalog_dedupe_link.py`.
2. **Защита от циклов в БД** — приложение обрывает цепочку; можно добавить CHECK или триггер (сложно в PG для произвольной глубины).
3. **Rate limit** — при `WRA_RATE_LIMIT_PUBLIC_PER_MINUTE>0` без Redis и нескольких воркеров лимит «рвётся»; в проде задать `WRA_RATE_LIMIT_REDIS_URI` или общий Redis.
4. **X-Forwarded-For** — `WRA_RATE_LIMIT_TRUST_FORWARDED_FOR` только за **доверенным** прокси, иначе риск обхода лимита.
5. **OTEL** — спаны Meili/PG в `search.py` через `tracing_ops` (без OTEL пакета — no-op).
6. **CODEOWNERS** — при переносе репо в организацию заменить `@danyaleyman` на `@org/team`.
7. **Job metrics** — обёртка `deploy/scripts/run_with_prometheus_job_metrics.sh`.
8. **E2E** — smoke «миграция 008 применена» в CI (миграция на ephemeral Postgres) — по желанию.

## Связанные документы

- `backend/docs/BLOCK_L_DEDUP.md`, `BLOCK_M_SCALE_COST.md`, `BLOCK_N_GOVERNANCE.md`
- `docs/AUDIT_REPO_FULL_STACK.md`, `backend/docs/RELEASE_CHECKLIST_CATALOG.md`
