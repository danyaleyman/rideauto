# Sprint B: Load Test + DB Tuning

## Goal

- Validate reliability under sustained traffic.
- Measure p50/p95/p99 and error rates for core catalog APIs.
- Detect index/vacuum bottlenecks and prioritize DB tuning.

## 1) Choose a sample car_id

```bash
cd /opt/prod-encar
docker-compose exec -T postgres psql -U wra -d wra -Atc "SELECT car_id FROM cars ORDER BY random() LIMIT 1;"
```

## 2) Run API load profile

```bash
cd /opt/prod-encar
python3 deploy/scripts/load_profile.py \
  --base-url http://127.0.0.1:8080 \
  --car-id "<SAMPLE_CAR_ID>"
```

The script runs 4 scenarios (`warmup`, 50/100/200 RPS) and prints:

- `ok_rate`
- `err_5xx_rate`, `err_4xx_rate`, `net_err_rate`
- `mean_ms`, `p50_ms`, `p95_ms`, `p99_ms`

## 3) Run PostgreSQL index audit

```bash
cd /opt/prod-encar
docker-compose exec -T postgres psql -U wra -d wra -f /dev/stdin < deploy/scripts/pg_index_audit.sql
```

Look for:

- high `seq_scan_pct` on hot tables
- large indexes with near-zero `idx_scan`
- high dead tuples and stale analyze/vacuum timestamps

## 4) Done criteria (Sprint B)

- Baseline report captured for 50/100/200 RPS.
- p95 endpoints compared against SLO targets:
  - `/api/search` < 350ms
  - `/api/car/{id}` < 250ms
- DB index/vacuum action list prepared (top 3 SQL fixes).
- Re-run load profile after tuning and record before/after deltas.
