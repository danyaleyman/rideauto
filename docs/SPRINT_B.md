# Sprint B: Load Test + DB Tuning

## Goal

- Validate reliability under sustained traffic.
- Measure p50/p95/p99 and error rates for core catalog APIs.
- Detect index/vacuum bottlenecks and prioritize DB tuning.

## 1) Choose a sample car_id

```bash
cd /opt/rideauto
docker-compose exec -T postgres psql -U wra -d wra -Atc "SELECT car_id FROM cars ORDER BY random() LIMIT 1;"
```

## 2) Run API load profile

```bash
cd /opt/rideauto
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
cd /opt/rideauto
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

## 5) Next execution steps (after first green baseline)

1. Run a stability soak by repeating the standard profile 10 times:

```bash
cd /opt/rideauto
for i in $(seq 1 10); do
  echo "==> run $i/10"
  python3 deploy/scripts/load_profile.py \
    --base-url http://127.0.0.1:8080 \
    --car-id "<SAMPLE_CAR_ID>"
done
```

2. During soak, monitor API errors and container restarts:

```bash
cd /opt/rideauto
docker-compose ps
docker-compose logs --tail=200 api
```

3. Apply top SQL/index actions from `pg_index_audit.sql` output.
4. Re-run standard 50/100/200 profile and compare p95/p99 deltas to baseline from `2026-04-07`.

## 6) Compose V2 + Next.js `web` (ops)

1. Install the Compose plugin on the server (Ubuntu): see **`deploy/DEPLOY.md`** → «Установка Compose V2».

2. Build and start `web` after `api` is healthy:

```bash
cd /opt/rideauto
git pull
docker compose build web
docker compose up -d web
docker compose ps
```

3. Smoke (replace host if nginx terminates TLS elsewhere):

```bash
curl -fsS "http://127.0.0.1:8080/api/health"
curl -sS -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:3000/catalog"
curl -sS -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:3000/"
```

4. Sprint B remainder (after API+web are green):

- Record **top 3** follow-ups from `pg_index_audit.sql` (even if «no change now»).
- If you applied SQL/index changes, **re-run** `load_profile.py` and append a short note under `docs/SLO.md` or your runbook.

Throughout this doc, **`docker compose`** (v2) and **`docker-compose`** (v1) use the same subcommands; prefer v2 to avoid `ContainerConfig` recreate bugs.

## 7) Shrink `web` build context

Root **`.dockerignore`** shrinks the Docker build context: **`web/node_modules`**, **`web/.next`**, тяжёлые каталоги вроде **`deploy/`**, **`docs/`**, **`infrastructure/`** (см. файл). After changing ignore rules, rebuild:

```bash
docker compose build web
```

## 8) After Sprint B (prod edge)

1. Set **`.env`**: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_SITE_URL` for the public domain.
2. Configure **nginx** (see `deploy/nginx/`) — site → `127.0.0.1:3000`, `/api/` → `127.0.0.1:8080` or your upstreams.
3. Smoke from outside: `/`, `/catalog`, `/api/health`.
4. Optional: add **`/api/similar`** to a small synthetic check or extend `load_profile.py` later.

## Sprint B closeout (recorded)

DB audit snapshot (`pg_index_audit.sql`) — **топ‑3 наблюдения**, действия при необходимости:

1. **`brands`**: высокий `seq_scan_pct` (~95%) при ~220 строках — для нагрузки **несущественно**, отдельная оптимизация не обязательна.
2. **`cars`**: много индексов с **`idx_scan = 0`** (в т.ч. крупный `idx_cars_data_gin`) — не удалять «вслепую»; пересмотр после стабильного прод‑трафика (при необходимости `EXPLAIN` по горячим запросам).
3. **`car_images`**: `dead_rows` порядка десятков тысяч — **autovacuum** уже активен; при росте мёртвых строк держать на контроле `last_autovacuum` / нагрузку диска.

Формально Sprint B закрыт, когда: baseline load зафиксирован, аудит прогнан, список выше принят, прод‑чеклист из **`deploy/DEPLOY.md`** (`.env` + nginx + внешний smoke) выполнен или назначен ответственным.
