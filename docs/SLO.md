# SLO / SLI Baseline (Sprint A)

## Targets

- Uptime: `99.9%` monthly for public API (`/api/health`, `/api/search`, `/api/car/*`)
- Search latency: `p95 /api/search < 350ms`
- Car latency: `p95 /api/car/{id} < 250ms`
- Error budget guard: `5xx rate < 1%` (5-minute rolling window)

## SLI Sources

- FastAPI + middleware metrics: `GET /metrics`
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
