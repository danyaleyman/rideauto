#!/usr/bin/env python3
"""Init local Postgres wra DB if needed."""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "infrastructure" / "postgresql" / "schema.sql"
DSN = "postgresql://wra:wra@127.0.0.1:5433/wra"


def main() -> int:
    try:
        conn = psycopg2.connect(DSN)
    except Exception as e:
        print(f"Cannot connect to {DSN}: {e}", file=sys.stderr)
        print("Create role/db: see deploy/scripts/local_build_databases.ps1", file=sys.stderr)
        return 1
    cur = conn.cursor()
    cur.execute("SELECT to_regclass('public.cars')")
    has_cars = cur.fetchone()[0]
    if has_cars:
        cur.execute("SELECT source, COUNT(*) FROM cars GROUP BY source ORDER BY source")
        print("Existing cars table:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
    else:
        print("Applying schema.sql …")
        sql = SCHEMA.read_text(encoding="utf-8")
        cur.execute(sql)
        conn.commit()
        print("Schema applied.")
    cur.execute("SELECT COUNT(*) FROM cars")
    print(f"Total cars: {cur.fetchone()[0]}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
