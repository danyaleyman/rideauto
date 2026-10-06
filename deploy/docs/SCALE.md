# Scale & capacity playbook (niche aggregator → growth)

Closes the “single-host will bite later” risk with a concrete ladder. Default deploy remains systemd + Docker on one VPS until SLOs burn.

## Tier 0 — current (canonical)

- API: multi-worker uvicorn behind nginx/CF
- Redis: required for rate limit + cache when workers > 1 (`WRA_REDIS_URL`)
- Meili: one primary; blue/green via `cars_build` + swap
- Catalog: `rideauto-catalog-pipeline.timer` only (ADR 0004)
- Outbox timer: near-realtime increments between full syncs

## Tier 1 — when search p95 SLO burns or 5xx spikes

1. Raise Meili RAM / disk; keep `WRA_MEILI_SWAP_INTO_LIVE=1`
2. API replicas (2+) sharing Redis + same Meili URL
3. PG: connection pooler (PgBouncer); read replica only if hydrate becomes bottleneck
4. CF cache for safe GET `/api/search` (see `CLOUDFLARE.md`)

## Tier 2 — multi-region / Avito-class (future)

- Meili replicas or shard by market (encar / che168 indexes)
- Separate scrape workers from API hosts
- Object storage for images CDN
- Full OTEL on prod (promotes ADR 0003)

## Readiness checks

```bash
curl -fsS http://127.0.0.1:8080/api/health
python backend/scripts/catalog_meili_consistency.py --strict
python deploy/scripts/load_profile.py --base-url https://YOUR_HOST --car-id EXAMPLE
```

## Done criterion

Architecture documents the ladder; Tier 0 is wired in-repo. Moving to Tier 1/2 is capacity work, not a missing platform layer.
