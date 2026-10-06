#!/usr/bin/env bash
# Operator prod gate checklist for Full Maturity Close-out.
# Run on the production host (or with tunnels). Does not mutate data unless noted.
set -euo pipefail
ROOT="${ROOT:-/opt/rideauto}"
echo "== RideAuto prod close-out gate =="
echo "1) Catalog pipeline units:"
systemctl is-enabled rideauto-catalog-pipeline.timer 2>/dev/null || echo "  (timer not enabled yet)"
echo "2) Lag metrics (if textfile present):"
ls -la /var/lib/node_exporter/textfile_collector/wra_catalog*.prom 2>/dev/null || echo "  (no lag prom yet — run pipeline once)"
echo "3) Resilience probes (needs network):"
echo "   cd $ROOT/backend && python scripts/resilience_probes.py --source encar"
echo "   cd $ROOT/backend && python scripts/resilience_probes.py --source che168"
echo "4) Meili pagination QA:"
echo "   python $ROOT/backend/scripts/meili_distinct_pagination_qa.py"
echo "5) PD retention dry-run:"
echo "   python $ROOT/backend/scripts/pd_retention_purge.py --dsn \"\$DATABASE_URL\""
echo "6) Fill: docs/CLOSEOUT_REVIEW_2026-10-06.md + deploy/docs/CLOUDFLARE.md + DR_RESTORE_DRILL.md"
echo "Done (printed next steps)."
