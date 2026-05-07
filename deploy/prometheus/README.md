# Prometheus: правила алертов RideAuto

Файл [`alert_rules_rideauto.yml`](alert_rules_rideauto.yml) содержит примеры:

- p95 latency и размер ответа **`/api/search`**
- доля **5xx** на маршрутах каталога
- **`wra_job_last_exit_code`** ≠ 0 (textfile от [`backend/scripts/prometheus_job_textfile.py`](../../backend/scripts/prometheus_job_textfile.py))
- «застой» по **`wra_job_last_completion_unixtime`** для типовых `JOB_NAME`
- health-алерты для Che168 scraper (`che168_http_*`, `che168_scraper_*`)

## Подключение

В `prometheus.yml`:

```yaml
rule_files:
  - /path/to/rideauto/deploy/prometheus/alert_rules_rideauto.yml
```

## Настройка job-имён

В обёртке [`deploy/scripts/run_with_prometheus_job_metrics.sh`](../scripts/run_with_prometheus_job_metrics.sh) задайте **`JOB_NAME`** так же, как в правилах (`wra_meilisearch_sync`, `wra_postgres_catalog_sync`), либо измените селекторы в YAML.

## Метрики HTTP

Имена и `path_group`: см. [`backend/docs/BLOCK_M_SCALE_COST.md`](../../backend/docs/BLOCK_M_SCALE_COST.md).

## Grafana

Импортируйте дашборд или создайте панели по `wra_http_request_duration_seconds`, `wra_http_requests_total`, `wra_job_*`.

Для China/Che168 добавьте панели:

- `che168_http_requests_total`, `che168_http_final_http_errors_total`
- `che168_http_circuit_breaker_opened_total`, `che168_http_circuit_breaker_short_circuit_total`
- `che168_scraper_detail_fail_total`, `che168_scraper_parse_fail_total`, `che168_scraper_saved_total`

Для Korea/Encar добавьте панели:

- `encar_http_requests_total`, `encar_http_final_http_errors_total`
- `encar_http_circuit_breaker_opened_total`, `encar_http_circuit_breaker_short_circuit_total`
- `encar_scraper_detail_fail_total`, `encar_scraper_parse_fail_total`, `encar_scraper_saved_total`
