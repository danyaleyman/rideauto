#!/usr/bin/env python3
"""Pricing queue + dual-run gate helpers for Catalog Truth Platform.

Writes Prometheus textfile metrics and optionally fails on dual-run thresholds.

Examples:
  python scripts/pricing_truth_metrics.py --dsn "$DATABASE_URL"
  python scripts/pricing_truth_metrics.py --dual-run --limit 500 --max-row-diff-pct 2
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import psycopg2
except ImportError:
    print("Install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

_BACKEND = Path(__file__).resolve().parents[1]


def _count(dsn: str, sql: str) -> int:
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0
    finally:
        conn.close()


def write_metrics(path: str, queued: int, old_rules: int) -> None:
    lines = [
        "# HELP wra_pricing_needs_recompute_rows Cars flagged for pricing recompute",
        "# TYPE wra_pricing_needs_recompute_rows gauge",
        f"wra_pricing_needs_recompute_rows {queued}",
        "# HELP wra_pricing_old_rules_version_approx Approx rows with stale pricing_rules_version (Encar heuristic)",
        "# TYPE wra_pricing_old_rules_version_approx gauge",
        f"wra_pricing_old_rules_version_approx {old_rules}",
        "# HELP wra_pricing_truth_metrics_unixtime Last metrics write",
        "# TYPE wra_pricing_truth_metrics_unixtime gauge",
        f"wra_pricing_truth_metrics_unixtime {int(time.time())}",
        "",
    ]
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="")
    ap.add_argument(
        "--textfile",
        default=os.environ.get("WRA_PRICING_TRUTH_TEXTFILE", ""),
        help="Prometheus textfile path",
    )
    ap.add_argument("--dual-run", action="store_true", help="Run semantic dual-run gate")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--max-row-diff-pct", type=float, default=2.0)
    args = ap.parse_args()
    dsn = (args.dsn or "").strip() or os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("need --dsn or DATABASE_URL", file=sys.stderr)
        return 2

    queued = _count(dsn, "SELECT COUNT(*) FROM cars WHERE needs_pricing_recompute IS TRUE")
    # Heuristic: missing pricing_clean or empty rules version marker
    old_rules = _count(
        dsn,
        """
        SELECT COUNT(*) FROM cars
        WHERE source = 'encar'
          AND (
            data->'pricing_clean' IS NULL
            OR COALESCE(data->'pricing_clean'->>'pricing_rules_version','') = ''
          )
        """,
    )
    textfile = (args.textfile or "").strip()
    if textfile:
        write_metrics(textfile, queued, old_rules)
    print(f"pricing_truth: needs_recompute={queued} old_rules_approx={old_rules}", flush=True)

    if args.dual_run:
        cmd = [
            sys.executable,
            str(_BACKEND / "scripts" / "dual_run_clean_vs_legacy.py"),
            "--limit",
            str(args.limit),
            "--semantic",
            "--max-row-diff-pct",
            str(args.max_row_diff_pct),
        ]
        env = dict(os.environ)
        env["DATABASE_URL"] = dsn
        print("pricing_truth: dual-run", " ".join(cmd), flush=True)
        proc = subprocess.run(cmd, env=env, check=False)
        return int(proc.returncode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
