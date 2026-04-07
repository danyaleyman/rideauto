# Мониторинг, нагрузка через nginx, операционка

Связано с **`docs/SLO.md`**. Цель: снимать SLI с **`GET /metrics`**, гонять **`load_profile.py`** по публичному URL и не светить метрики в интернет без защиты.

## 1) Эндпоинт Prometheus

- **`GET /metrics`** (включается **`WRA_METRICS_ENABLED=true`**, по умолчанию так).
- Имена метрик (prefix **`wra_`**):
  - **`wra_http_request_duration_seconds`** — histogram, labels `method`, `path_group`
  - **`wra_http_requests_total`** — counter, labels `method`, `path_group`, `status_class` (`2xx`, `4xx`, `5xx`, …)
  - **`wra_cache_lookups_total`** — counter, `segment`, `result` (`hit` / `miss`)

`path_group` нормализуется (например `/api/car/{id}`), чтобы не раздувать кардинальность.

## 2) Как скрапить безопасно

**Рекомендуется:** Prometheus (или агент) на **том же хосте**, что и Docker, бьёт в **loopback**:

```yaml
# fragment: prometheus.yml scrape_configs
  - job_name: prod-encar-api
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:8080"]
```

Тогда **не нужно** вывешивать `/metrics` на `https://rideauto.ru`. Если метрики нужны только с другой машины — используйте VPN / SSH tunnel / отдельный internal listener, либо **`deploy/nginx/location-metrics-proxy.snippet.conf`** с ограничением по IP.

## 3) Алерты (идеи под PromQL)

Точные выражения зависят от версии Prometheus и ваших recording rules. Ориентиры из **`docs/SLO.md`**:

- **Доля 5xx** за 5m > 1%: по `wra_http_requests_total` с label `status_class="5xx"`.
- **p95 latency** `/api/search` и `/api/car/{id}`: из `wra_http_request_duration_seconds` + `histogram_quantile(0.95, …)` с фильтром по `path_group`.

Сделайте **тестовый firing**: временно снизьте порог или используйте `curl` к тестовому rule в Alertmanager.

## 4) Нагрузка «как пользователь» (через nginx / TLS)

Из корня репозитория на сервере (или с машины, которой разрешён доступ к API по HTTPS):

```bash
python3 deploy/scripts/load_profile.py \
  --base-url https://rideauto.ru \
  --car-id "dongchedi-22752383"
```

При самоподписанном сертификате или корпоративном CA:

```bash
python3 deploy/scripts/load_profile.py \
  --base-url https://rideauto.ru \
  --car-id "dongchedi-22752383" \
  --insecure
```

Сравнивайте p95/p99 с baseline в **`docs/SLO.md`**; рост допустим из-за TLS и кэша nginx.

## 5) Бэкап PostgreSQL (Compose)

```bash
cd /opt/prod-encar
./deploy/scripts/backup_postgres_compose.sh
```

По умолчанию каталог **`./backups/`** (создаётся скриптом). Крон: раз в сутки + ротация старых файлов на ваше усмотрение.

## 6) Секреты и пароли

- Не коммить **`.env`**. Ключи, попавшие в чат/логи, **ротировать**.
- В проде сменить дефолтные **`POSTGRES_PASSWORD`**, **`MEILI_MASTER_KEY`**, при необходимости Redis; синхронно обновить **`WRA_PG_DSN`** и перезапустить **`api`**.

## 7) Многопроцессный uvicorn

Если когда-нибудь включите **несколько воркеров** и **`PROMETHEUS_MULTIPROC_DIR`**, читайте комментарий в **`backend/fastapi_app/metrics/prometheus.py`** (MultiProcessCollector).
