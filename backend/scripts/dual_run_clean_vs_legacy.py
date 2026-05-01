#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg2
import psycopg2.extras

from read_models import build_catalog_read_model


def _dsn() -> str:
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    return dsn


def run(limit: int) -> dict[str, Any]:
    stats = {"checked": 0, "price_diff": 0, "fuel_diff": 0, "transmission_diff": 0, "drive_type_diff": 0}
    sample: list[dict[str, Any]] = []
    with psycopg2.connect(_dsn()) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT car_id, data
                FROM cars
                WHERE source='encar'
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (max(1, limit),),
            )
            for row in cur.fetchall():
                data = row.get("data") if isinstance(row.get("data"), dict) else {}
                legacy = build_catalog_read_model(data, use_clean=False)
                clean = build_catalog_read_model(data, use_clean=True)
                stats["checked"] += 1
                diff_fields = []
                if legacy.get("price_rub") != clean.get("price_rub"):
                    stats["price_diff"] += 1
                    diff_fields.append("price_rub")
                if legacy.get("engine_type") != clean.get("engine_type"):
                    stats["fuel_diff"] += 1
                    diff_fields.append("engine_type")
                if legacy.get("transmission_type") != clean.get("transmission_type"):
                    stats["transmission_diff"] += 1
                    diff_fields.append("transmission_type")
                if legacy.get("drive_type") != clean.get("drive_type"):
                    stats["drive_type_diff"] += 1
                    diff_fields.append("drive_type")
                if diff_fields and len(sample) < 25:
                    sample.append({"car_id": row.get("car_id"), "fields": diff_fields, "legacy": legacy, "clean": clean})
    return {"stats": stats, "sample": sample}


def main() -> None:
    ap = argparse.ArgumentParser(description="Dual-run diff: clean vs legacy read model")
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()
    print(json.dumps(run(limit=int(args.limit)), ensure_ascii=False))


if __name__ == "__main__":
    main()

