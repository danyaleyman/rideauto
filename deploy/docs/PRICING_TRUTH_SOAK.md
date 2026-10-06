# Pricing & Read-Model Truth — prod soak / rollout gate

См. также [`BLOCK_D_CLEAN_ROLLOUT.md`](../../backend/docs/BLOCK_D_CLEAN_ROLLOUT.md), [`LEGACY_RETIREMENT_PLAN.md`](../../backend/docs/LEGACY_RETIREMENT_PLAN.md).

## Env (цель после soak)

```bash
WRA_CLEAN_READ_MODE=1
WRA_CLEAN_READ_PERCENT=100
WRA_LEGACY_FALLBACKS_ENABLED=0   # только после canary
```

## Перед каждым bump percent

```bash
cd /opt/rideauto/backend
export DATABASE_URL=...
python scripts/dual_run_clean_vs_legacy.py --limit 500 --semantic --max-row-diff-pct 2
python scripts/pricing_truth_metrics.py --dsn "$DATABASE_URL" \
  --textfile /var/lib/node_exporter/textfile_collector/wra_pricing_truth.prom
```

Алерты: `RideautoPricingRecomputeQueueHigh` в `deploy/prometheus/alert_rules_rideauto.yml`.

## Soak log (заполнить на проде)

| Date | Percent | Fallbacks | dual-run pct_diff | Notes | Operator |
|------|---------|-----------|-------------------|-------|----------|
|      | 10      | 1         |                   |       |          |
|      | 50      | 1         |                   |       |          |
|      | 100     | 1         |                   | start soak | |
|      | 100     | 0         |                   | canary fallbacks off | |

**Done:** 14 дней (или согласованный срок) на 100% clean без rollback; queue `needs_pricing_recompute` сходится после catalog pipeline; fallbacks off.
