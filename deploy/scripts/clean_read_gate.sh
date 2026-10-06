#!/usr/bin/env bash
# Clean-read Go/No-Go gate (semantic dual-run). Exit 0 only if within threshold.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/backend"
export PYTHONPATH="${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
DSN="${DATABASE_URL:?DATABASE_URL required}"
LIMIT="${WRA_CLEAN_GATE_LIMIT:-500}"
MAX_PCT="${WRA_CLEAN_GATE_MAX_ROW_DIFF_PCT:-2}"
python scripts/dual_run_clean_vs_legacy.py --limit "$LIMIT" --semantic --max-row-diff-pct "$MAX_PCT"
echo "clean_read_gate: OK"
