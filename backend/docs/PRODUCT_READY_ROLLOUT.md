# Product Ready Rollout

## Flags

- `WRA_CLEAN_READ_MODE` - master switch for clean-first reads.
- `WRA_CLEAN_READ_PERCENT` - rollout percentage (0-100), deterministic by key hash.
- `WRA_LEGACY_FALLBACKS_ENABLED` - fallback to legacy fields during migration.
- `WRA_API_CONTRACT_VERSION` - response contract label (`v1`, `v2`).

## Rollout sequence

1. Staging: `WRA_CLEAN_READ_MODE=1`, `WRA_CLEAN_READ_PERCENT=100`.
2. Production canary: `WRA_CLEAN_READ_MODE=1`, `WRA_CLEAN_READ_PERCENT=10`.
3. Production half: `WRA_CLEAN_READ_PERCENT=50`.
4. Full rollout: `WRA_CLEAN_READ_PERCENT=100`.
5. Legacy retirement prep: keep clean on 100% for 14 days, then disable fallbacks.

## Go/No-Go checks per step

- `encar_parser_audit.py --fail-on-regression` returns `0`.
- Dual-run diff (`dual_run_clean_vs_legacy.py`) has no unexpected spikes.
- Search/facets endpoints have no error-rate increase.
- Price intent shares stay within threshold deltas.

