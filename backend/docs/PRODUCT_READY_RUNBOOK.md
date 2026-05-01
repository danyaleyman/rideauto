# Product Ready Runbook

## SLOs

- Parser schema coverage: `pct_schema_version >= 95%`.
- Missing required fields: `pct_missing_required <= 2%`.
- Monthly/reserved share drift: within configured deltas.
- Meili preflight coverage:
  - price coverage >= 97%
  - brand coverage >= 99%
  - model coverage >= 99%

## Nightly commands

- Parser audit:
  - `python backend/scripts/encar_parser_audit.py --fail-on-regression --history-file backend/data/encar_parser_audit_history.jsonl`
- Price-intent case check:
  - `python backend/scripts/encar_price_intent_case_check.py --config scraper_config.yaml --cases-file backend/data/encar_price_intent_cases.json`

## Incident handling

1. Freeze rollout: set `WRA_CLEAN_READ_PERCENT=0`.
2. Re-run parser audit and dual-run diff.
3. If parser regression: run `reprocess_from_raw_envelope.py` on affected sample.
4. If search regression: run Meili sync with preflight gate, verify output before publish.
5. Postmortem: add/adjust regression test and threshold.

## Ownership matrix

- Parser + normalization: backend parser owners.
- API contracts: fastapi owners.
- Search index + preflight gates: search/indexing owners.
- Nightly jobs + alerts: infrastructure owners.

