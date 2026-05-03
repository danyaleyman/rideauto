# Блок M — масштаб и стоимость

## Горячие пути

- Поиск и фасеты: Meilisearch + Redis JSON-кэш (`fastapi_app/cache.py`, эпоха `WRA_CATALOG_CACHE_EPOCH` / `cache_epoch.py`).
- Карточка: `GET /api/car`, гидратация Postgres, кэш по ключу с эпохой.
- Обогащение терминов: Redis KV + опционально PG (`catalog_enrich_*` в `config.py`).
- **Tracing**: опционально OpenTelemetry FastAPI → OTLP HTTP (`WRA_OTEL_*`, `fastapi_app/otel_tracing.py`). В горячем пути поиска — спаны `meilisearch.*` и `postgres.fetch_cars_by_ids*` (`fastapi_app/tracing_ops.py`).
- **Rate limit**: публичные GET каталога — `slowapi` (`WRA_RATE_LIMIT_PUBLIC_PER_MINUTE`, см. `deploy/env.rideauto.example`). При **нескольких воркерах** задайте **`WRA_RATE_LIMIT_REDIS_URI`** или общий **`WRA_REDIS_URL`** — иначе лимит считается отдельно в каждом процессе.

## Ориентиры бюджетов (настройки по умолчанию)

| Зона | Параметр | Default | Комментарий |
|------|-----------|---------|-------------|
| Search | `cache_ttl_search_sec` | 10 | короткий TTL из-за частоты смены выдачи |
| Facets | `cache_ttl_facets_sec` | 30 | |
| Car | `cache_ttl_car_sec` | 60 | |
| Enrich pair | `catalog_enrich_pair_redis_ttl_sec` | ~30 суток | снижает нагрузку на LLM/внешние вызовы |

## Мониторинг batch/sync (cron)

- Скрипт **`backend/scripts/prometheus_job_textfile.py`** пишет gauge-метрики в файл для **node_exporter textfile collector** (`WRA_JOB_METRICS_TEXTFILE`, `JOB_NAME`, `EXIT_CODE`, `DURATION_SEC`).
- Готовая обёртка: **`deploy/scripts/run_with_prometheus_job_metrics.sh`** (задаёт `DURATION_SEC`, вызывает `prometheus_job_textfile.py`).
- Примеры правил Prometheus: **`deploy/prometheus/alert_rules_rideauto.yml`** (HTTP + `wra_job_*`).
- В systemd можно дополнительно использовать `OnFailure=` для алертов.

## Наблюдаемость (Prometheus)

Экспорт: **`GET /metrics`** (`WRA_METRICS_ENABLED`).

| Метрика | Назначение |
|---------|------------|
| `wra_http_request_duration_seconds` | Latency по `method`, `path_group` — **p95/p99 в Grafana** |
| `wra_http_requests_total` | Объём и классы статусов `2xx`/`4xx`/`5xx` |
| `wra_http_response_body_bytes` | Размер тела ответа (если Starlette уже материализовал `body`; streaming может не попасть). Отключение: `WRA_METRICS_RESPONSE_BODY_BYTES_ENABLED=false` |
| `wra_cache_lookups_total` | hit/miss по сегментам Redis-кэша |

### Примеры PromQL (ориентиры для алертов)

Настройте пороги под свой трафик; ниже — шаблоны.

**p95 latency для поиска (за 5 мин):**

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(wra_http_request_duration_seconds_bucket{path_group="/api/search"}[5m])
  )
)
```

**Доля 5xx по каталогу:**

```promql
sum(rate(wra_http_requests_total{status_class="5xx", path_group=~"/api/(search|car.*|facets).*"}[5m]))
/
sum(rate(wra_http_requests_total{path_group=~"/api/(search|car.*|facets).*"}[5m]))
```

**p95 размер ответа search (если метрика собирается):**

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(wra_http_response_body_bytes_bucket{path_group="/api/search"}[5m])
  )
)
```

Рекомендация: завести дашборд «Catalog API» и подключить **`deploy/prometheus/alert_rules_rideauto.yml`** (или скопировать выражения в свой репозиторий правил).

## Синк Meili

- `WRA_MEILI_PREFLIGHT_GATE` и покрытие цен — см. `docs/PRICING_PIPELINE.md`.

## Рост индекса

- Размер документа Meili зависит от полей в `sync_meilisearch.py`; новые фильтруемые поля = рост RAM и времени индексации.
