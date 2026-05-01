# Legacy Retirement Plan

## Preconditions

- `WRA_CLEAN_READ_MODE=1` and `WRA_CLEAN_READ_PERCENT=100` for 14 consecutive days.
- Nightly parser audit passes for 14 consecutive days.
- Dual-run diff reviewed and approved.

## Retirement phases

1. Keep clean mode 100%, set `WRA_LEGACY_FALLBACKS_ENABLED=1` (stability soak).
2. Canary disable fallback (`WRA_LEGACY_FALLBACKS_ENABLED=0`) in staging.
3. Production canary disable fallback for 10% traffic.
4. Full disable fallback after no regressions.

## Decommission tasks

- Remove legacy field reads from:
  - `catalog_pg_core`
  - `catalog_slim`
  - Meili sync mapper
- Keep migration window for one release cycle with rollback flag.
- Remove fallback flag only after one stable release.

