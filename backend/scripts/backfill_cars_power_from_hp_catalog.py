#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from catalog_export_utils import fill_power_from_external


def _dsn(args_dsn: str) -> str:
    return (args_dsn or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN") or "").strip()


def _parse_hp(data: Dict[str, Any]) -> Optional[int]:
    for key in ("power", "power_hp", "hp", "outputHorsepower"):
        v = data.get(key)
        if v is None or v == "":
            continue
        try:
            if isinstance(v, str):
                digits = "".join(ch for ch in v if ch.isdigit())
                if not digits:
                    continue
                hp = int(digits)
            else:
                hp = int(float(v))
            if 20 <= hp <= 2500:
                return hp
        except (TypeError, ValueError):
            continue
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill cars.power_hp and data.power from hp_catalog")
    p.add_argument("--dsn", default="", help="PostgreSQL DSN (or DATABASE_URL/WRA_PG_DSN)")
    p.add_argument("--source", default="encar", help="cars.source filter (encar, dongchedi, *, ...)")
    p.add_argument("--batch-size", type=int, default=2000, help="Batch size")
    p.add_argument("--max-rows", type=int, default=0, help="Limit processed rows (0 = all)")
    args = p.parse_args()

    dsn = _dsn(args.dsn)
    if not dsn:
        print("PostgreSQL DSN is required: --dsn or DATABASE_URL/WRA_PG_DSN")
        return 2

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    processed = 0
    updated = 0
    skipped = 0
    last_id = 0

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            while True:
                if args.max_rows > 0 and processed >= args.max_rows:
                    break
                left = args.batch_size
                if args.max_rows > 0:
                    left = min(left, args.max_rows - processed)

                where_source = ""
                params: list[Any] = [last_id]
                if args.source and args.source != "*":
                    where_source = "AND source = %s"
                    params.append(args.source)
                params.append(left)

                cur.execute(
                    f"""
                    SELECT id, car_id, data, power_hp
                    FROM cars
                    WHERE id > %s
                      {where_source}
                      AND (
                        power_hp IS NULL OR power_hp <= 0
                        OR NULLIF(trim(COALESCE(data->>'power', '')), '') IS NULL
                      )
                    ORDER BY id ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
                if not rows:
                    break

                for row in rows:
                    rid = int(row["id"])
                    last_id = rid
                    processed += 1

                    payload = row["data"]
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except Exception:
                            skipped += 1
                            continue
                    if not isinstance(payload, dict):
                        skipped += 1
                        continue

                    before_hp = _parse_hp(payload)
                    fill_power_from_external(payload)
                    after_hp = _parse_hp(payload)
                    if after_hp is None:
                        skipped += 1
                        continue

                    if before_hp == after_hp and row.get("power_hp") == after_hp:
                        skipped += 1
                        continue

                    cur.execute(
                        """
                        UPDATE cars
                        SET data = %s,
                            power_hp = %s,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (psycopg2.extras.Json(payload), int(after_hp), rid),
                    )
                    updated += 1

                conn.commit()
                print(
                    f"progress processed={processed} updated={updated} skipped={skipped} last_id={last_id}",
                    flush=True,
                )
    finally:
        conn.close()

    print(f"done processed={processed} updated={updated} skipped={skipped}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

