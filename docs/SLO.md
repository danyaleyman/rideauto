# SLO / SLI Baseline (Sprint A)

## Targets

- Uptime: `99.9%` monthly for public API (`/api/health`, `/api/search`, `/api/car/*`)
- Search latency: `p95 /api/search < 350ms`
- Car latency: `p95 /api/car/{id} < 250ms`
- Error budget guard: `5xx rate < 1%` (5-minute rolling window)

## SLI Sources

- FastAPI + middleware metrics: `GET /metrics` (плейбук: **`docs/MONITORING.md`**)
- HTTP health checks: `GET /api/health`
- Synthetic smoke checks from server side (`deploy/scripts/post_migration_check.sh`)
- Frontend RUM: `POST /api/web-vitals`, summary via `GET /api/ops/web-vitals-summary`

## Alerting Baseline

- `api_5xx_spike`: 5xx ratio > `1%` for 5m
- `api_search_p95_slow`: p95 `/api/search` > `350ms` for 10m
- `api_car_p95_slow`: p95 `/api/car/*` > `250ms` for 10m
- `empty_search_anomaly`: `/api/search` non-empty queries with zero results above normal band
- `index_stale`: Meili indexed docs significantly lower than `cars` rows in PostgreSQL

## Review Cadence

- Daily during migration week
- Weekly once platform stabilizes

## Definition of Done (Sprint A)

- SLO targets and formulas documented and accepted
- Monitoring dashboards expose p95 + 5xx + cache hit ratio
- Alerts configured and test-triggered at least once
- Runbook includes cutover and rollback with command-level steps

## Baseline Run (2026-04-07)

Load profile command:

```bash
python3 deploy/scripts/load_profile.py \
  --base-url http://127.0.0.1:8080 \
  --car-id "che168-EXAMPLE"
```

Preflight:

- `GET /api/health`: `200`
- `GET /api/search?per_page=1`: `200`
- `GET /api/car/che168-EXAMPLE`: `200`

Scenarios:

- `warmup` (20 RPS, 20s): requests `400`, ok `100%`, p95 `47.0ms`, p99 `116.5ms`
- `rps-50` (50 RPS, 60s): requests `3000`, ok `100%`, p95 `49.0ms`, p99 `106.2ms`
- `rps-100` (100 RPS, 60s): requests `6000`, ok `100%`, p95 `49.3ms`, p99 `66.9ms`
- `rps-200` (200 RPS, 60s): requests `12000`, ok `100%`, p95 `44.7ms`, p99 `50.1ms`

Outcome:

- `err_5xx_rate = 0%`, `err_4xx_rate = 0%`, `net_err_rate = 0%` on all stages.
- Current baseline is comfortably within Sprint A latency/error targets.

## Stack note (API + Next `web`)

Docker Compose brings up **`api`** (`:8080`) and **`web`** (`:3000`). External SLO applies to what users hit via **nginx** (or equivalent): confirm **`NEXT_PUBLIC_API_BASE`**, **`NEXT_PUBLIC_SITE_URL`**, and TLS after cutover. Re-run `load_profile.py` against the API URL that nginx forwards to, if that path differs from loopback.

## Baseline via public HTTPS (`https://rideauto.ru`)

Run from app server (path includes **TLS + nginx + сеть**; микс **~75%** `/api/search`, **~25%** `/api/car/{id}`):

```bash
python3 deploy/scripts/load_profile.py \
  --base-url https://rideauto.ru \
  --car-id "che168-EXAMPLE"
```

Preflight (server → публичный домен):

- `GET /api/health`: `200` (~64 ms)
- `GET /api/search?per_page=1`: `200` (~132 ms)
- `GET /api/car/che168-EXAMPLE`: `200` (~80 ms)

Scenarios:

- `warmup` (20 RPS, 20s): requests `400`, ok `100%`, p95 `116 ms`, p99 `182 ms`
- `rps-50` (50 RPS, 60s): requests `3000`, ok `100%`, p95 `57 ms`, p99 `75 ms`
- `rps-100` (100 RPS, 60s): requests `6000`, ok `100%`, p95 `67 ms`, p99 `77 ms`
- `rps-200` (200 RPS, 60s): requests `12000`, ok `100%`, p95 `61 ms`, p99 `71 ms`

Outcome:

- `err_5xx_rate = 0%`, `err_4xx_rate = 0%`, `net_err_rate = 0%` on all stages.
- Blended p95 stays **well below** the Sprint A ceiling (`p95 /api/search < 350ms` — отдельные эндпоинты в этом скрипте не разнесены).
