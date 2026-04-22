#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   BASE_URL=http://127.0.0.1:8080 X_WRA_ADMIN_KEY=... ./deploy/scripts/collect_catalog_filter_diagnostics.sh 120 2000 /tmp/catalog-filter-events.json
# Args:
#   $1 minutes window (default: 180)
#   $2 max events (default: 2000)
#   $3 output file (default: /tmp/catalog-filter-events-<timestamp>.json)

MINUTES="${1:-180}"
LIMIT="${2:-2000}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="${3:-/tmp/catalog-filter-events-${STAMP}.json}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"

URL="${BASE_URL%/}/api/ops/catalog-filter-events?minutes=${MINUTES}&limit=${LIMIT}"
TMP_FILE="$(mktemp)"

if [[ -n "${X_WRA_ADMIN_KEY:-}" ]]; then
  curl -fsS -H "X-WRA-Admin-Key: ${X_WRA_ADMIN_KEY}" "$URL" > "$TMP_FILE"
else
  curl -fsS "$URL" > "$TMP_FILE"
fi

python -m json.tool "$TMP_FILE" > "$OUT_FILE"
rm -f "$TMP_FILE"

echo "Saved diagnostics dump: $OUT_FILE"
