#!/usr/bin/env python3
"""Auto-link high-confidence VIN duplicate groups (Entity Resolution Platform).

Only groups with catalog_dedupe_key starting with ``vin:`` and size >= 2 are linked.
Other groups are written to a report file for ops.

Examples:
  python scripts/catalog_dedupe_auto_apply.py --dsn "$DATABASE_URL" --dry-run
  python scripts/catalog_dedupe_auto_apply.py --dsn "$DATABASE_URL" --apply --report /tmp/dedupe_skip.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Tuple

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from catalog_dedupe import catalog_dedupe_key, listing_json_inner_from_cars_data  # noqa: E402


def _parse_ts(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, datetime):
        return v.timestamp()
    try:
        return float(v)
    except Exception:
        return 0.0


def _link(conn: Any, duplicate: str, canonical: str, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN link {duplicate} -> {canonical}", flush=True)
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cars
            SET dedupe_canonical_car_id = %s, updated_at = NOW()
            WHERE car_id = %s AND dedupe_canonical_car_id IS NULL
            """,
            (canonical, duplicate),
        )
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true", help="Apply VIN links (otherwise dry-run)")
    ap.add_argument("--min-size", type=int, default=2)
    ap.add_argument("--report", default="", help="JSONL path for non-VIN groups")
    ap.add_argument("--limit-groups", type=int, default=0)
    args = ap.parse_args()
    dry = args.dry_run or not args.apply
    dsn = (args.dsn or "").strip() or os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("need --dsn or DATABASE_URL", file=sys.stderr)
        return 2

    groups: DefaultDict[str, List[Tuple[str, float, str]]] = defaultdict(list)
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(name="wra_dedupe_auto", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.itersize = 4096
            cur.execute(
                """
                SELECT car_id, source, data, updated_at
                FROM cars
                WHERE dedupe_canonical_car_id IS NULL
                ORDER BY car_id
                """
            )
            for row in cur:
                cid = str(row.get("car_id") or "").strip()
                if not cid:
                    continue
                src = row.get("source")
                inner = listing_json_inner_from_cars_data(row.get("data"))
                key = catalog_dedupe_key(cid, str(src) if src is not None else None, inner)
                groups[key].append((cid, _parse_ts(row.get("updated_at")), str(src or "")))

        linked = 0
        skipped: List[Dict[str, Any]] = []
        auto_groups = 0
        # High-confidence: VIN and same-source inner id (not bare id:).
        def _auto_key(k: str) -> bool:
            return k.startswith("vin:") or k.startswith("source:")

        for key, items in groups.items():
            if len(items) < args.min_size:
                continue
            items_sorted = sorted(items, key=lambda x: (-x[1], x[0]))
            canonical = items_sorted[0][0]
            dups = [x[0] for x in items_sorted[1:]]
            if _auto_key(key):
                auto_groups += 1
                if args.limit_groups and auto_groups > args.limit_groups:
                    continue
                for dup in dups:
                    _link(conn, dup, canonical, dry_run=dry)
                    linked += 1
            else:
                skipped.append(
                    {
                        "dedupe_key": key,
                        "count": len(items),
                        "canonical_car_id": canonical,
                        "duplicate_car_ids": dups,
                    }
                )

        report_path = (args.report or "").strip()
        if report_path:
            with open(report_path, "w", encoding="utf-8") as f:
                for row in skipped:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"wrote skip report n={len(skipped)} -> {report_path}", flush=True)

        print(
            f"catalog_dedupe_auto: auto_groups={auto_groups} links={linked} "
            f"skipped_groups={len(skipped)} dry_run={dry}",
            flush=True,
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
