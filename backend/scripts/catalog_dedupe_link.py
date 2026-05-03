#!/usr/bin/env python3
"""Связать дубликат листинга с каноническим car_id в Postgres (cars.dedupe_canonical_car_id).

Пример:
  python scripts/catalog_dedupe_link.py --dsn "$DATABASE_URL" --duplicate encar-dup-1 --canonical encar-main-1

После связи: дубликат не попадает в Meilisearch (см. sync_meilisearch iter_car_rows); API отдаёт каноническую карточку.
"""
from __future__ import annotations

import argparse
import sys

try:
    import psycopg2
except ImportError:
    print("Install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    p = argparse.ArgumentParser(description="Set cars.dedupe_canonical_car_id for duplicate listing")
    p.add_argument("--dsn", default="", help="PostgreSQL URI (или DATABASE_URL)")
    p.add_argument("--duplicate", required=True, help="car_id дубликата")
    p.add_argument("--canonical", required=True, help="car_id канонической строки")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    dsn = (args.dsn or "").strip() or __import__("os").environ.get("DATABASE_URL", "")
    if not dsn:
        print("need --dsn or DATABASE_URL", file=sys.stderr)
        sys.exit(2)
    dup = str(args.duplicate).strip()
    can = str(args.canonical).strip()
    if not dup or not can or dup == can:
        print("invalid duplicate/canonical pair", file=sys.stderr)
        sys.exit(2)

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT car_id, dedupe_canonical_car_id FROM cars WHERE car_id = ANY(%s)",
                ([dup, can],),
            )
            rows = {str(r[0]): r[1] for r in cur.fetchall()}
            if can not in rows:
                print(f"canonical not found: {can!r}", file=sys.stderr)
                sys.exit(3)
            if dup not in rows:
                print(f"duplicate not found: {dup!r}", file=sys.stderr)
                sys.exit(3)
            if rows.get(can):
                print(f"warning: canonical {can!r} already has dedupe_canonical_car_id={rows[can]!r}", file=sys.stderr)
            if args.dry_run:
                print(f"dry-run: would set {dup!r} -> canonical {can!r}")
                return
            cur.execute(
                """
                UPDATE cars
                SET dedupe_canonical_car_id = %s, updated_at = now()
                WHERE car_id = %s
                """,
                (can, dup),
            )
            if cur.rowcount != 1:
                print(f"unexpected rowcount {cur.rowcount}", file=sys.stderr)
                sys.exit(4)
        conn.commit()
        print(f"linked duplicate {dup!r} -> canonical {can!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
