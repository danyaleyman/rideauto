#!/usr/bin/env python3
"""Пересчёт power/power_hp для гибридов в Postgres (enrich + опционально pricing sync)."""
from __future__ import annotations

import argparse
import json
import os
import sys

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from hybrid_power import enrich_hybrid_power_fields, is_hybrid_listing
from market_pricing_shared import classify_fuel


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill hybrid power fields in cars.data")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""))
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.dsn:
        print("DATABASE_URL or --dsn required", file=sys.stderr)
        return 2

    import psycopg2
    from psycopg2.extras import RealDictCursor

    updated = 0
    scanned = 0
    with psycopg2.connect(args.dsn, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, car_id, data
                FROM cars
                WHERE source = 'encar'
                  AND (
                    COALESCE(data->>'engine_type', data->'data'->>'engine_type', '') ILIKE '%%hybrid%%'
                    OR COALESCE(data->>'engine_type', data->'data'->>'engine_type', '') ILIKE '%%hev%%'
                    OR COALESCE(data->>'engine_type', data->'data'->>'engine_type', '') ILIKE '%%phev%%'
                    OR COALESCE(data->>'engine_type', data->'data'->>'engine_type', '') ILIKE '%%plug%%'
                    OR COALESCE(data->>'engine_type', data->'data'->>'engine_type', '') LIKE '%%+%%'
                    OR COALESCE(data->>'engine_type_ru', data->'data'->>'engine_type_ru', '') LIKE '%%+%%'
                    OR COALESCE(data->>'engine_type', data->'data'->>'engine_type', '') ILIKE '%%электри%%'
                    OR COALESCE(data->>'engine_type_ru', data->'data'->>'engine_type_ru', '') ILIKE '%%электри%%'
                  )
                ORDER BY id DESC
                LIMIT %s
                """,
                (args.limit,),
            )
            rows = cur.fetchall()
        for row in rows:
            scanned += 1
            payload = row.get("data")
            if not isinstance(payload, dict):
                continue
            inner = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            if not isinstance(inner, dict):
                continue
            if not is_hybrid_listing(inner) and classify_fuel(inner) != "hybrid":
                continue
            before_hp = inner.get("power_hp") or inner.get("power")
            before_ice = inner.get("power_ice_hp")
            before_ed = inner.get("power_electric_hp")
            if not enrich_hybrid_power_fields(inner):
                continue
            after_hp = inner.get("power_hp") or inner.get("power")
            if (
                str(before_hp) == str(after_hp)
                and before_ice == inner.get("power_ice_hp")
                and before_ed == inner.get("power_electric_hp")
                and inner.get("power_ice_hp") not in (None, "")
                and inner.get("power_electric_hp") not in (None, "")
            ):
                continue
            updated += 1
            if args.dry_run:
                print(row["car_id"], before, "->", inner.get("power"), inner.get("power_ice_hp"), inner.get("power_electric_hp"))
                continue
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE cars SET data = %s::jsonb, power_hp = %s, needs_pricing_recompute = TRUE WHERE id = %s",
                    (json.dumps(payload, ensure_ascii=False), inner.get("power_hp"), row["id"]),
                )
        if not args.dry_run:
            conn.commit()
    print(f"scanned={scanned} updated={updated} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
