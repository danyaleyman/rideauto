#!/usr/bin/env python3
"""Проставляет cars.year / cars.year_month для Che168 из yearname/regdate в JSON."""
from __future__ import annotations

import argparse
import json
import os
import sys

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from catalog_pg_core import row_to_car_fields


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""))
    p.add_argument("--limit", type=int, default=500_000)
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.dsn:
        print("DATABASE_URL or --dsn required", file=sys.stderr)
        return 2

    import psycopg2
    from psycopg2.extras import RealDictCursor

    updated = 0
    scanned = 0
    last_id = 0
    with psycopg2.connect(args.dsn, cursor_factory=RealDictCursor) as conn:
        while scanned < args.limit:
            chunk_limit = min(args.batch_size, args.limit - scanned)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, car_id, data, year, year_month
                    FROM cars
                    WHERE source = 'che168' AND id > %s
                    ORDER BY id ASC
                    LIMIT %s
                    """,
                    (last_id, chunk_limit),
                )
                rows = cur.fetchall()
            if not rows:
                break
            batch_updates: list[tuple] = []
            for row in rows:
                scanned += 1
                last_id = int(row["id"])
                payload = row.get("data")
                if not isinstance(payload, dict):
                    continue
                fields = row_to_car_fields(str(row["car_id"]), payload)
                new_y = fields.get("year")
                new_ym = fields.get("year_month")
                if new_ym is None:
                    continue
                if row.get("year_month") == new_ym and row.get("year") == new_y:
                    continue
                updated += 1
                if args.dry_run:
                    if updated <= 5:
                        print(row["car_id"], row.get("year_month"), "->", new_ym)
                    continue
                batch_updates.append((new_y, new_ym, row["id"]))
            if not args.dry_run and batch_updates:
                with conn.cursor() as cur:
                    for new_y, new_ym, rid in batch_updates:
                        cur.execute(
                            "UPDATE cars SET year = %s, year_month = %s, needs_pricing_recompute = TRUE WHERE id = %s",
                            (new_y, new_ym, rid),
                        )
                conn.commit()
                print(f"progress scanned={scanned} updated={updated}", flush=True)
    print(f"scanned={scanned} updated={updated} dry_run={args.dry_run}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
