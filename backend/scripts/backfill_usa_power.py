#!/usr/bin/env python3
"""
Бэкфилл мощности (л.с.) для USA-карточек Autotrader: NHTSA vPIC по VIN → data/us_engine_map.json.

Зачем: ~474 карточки с displacement_cc, но без power_hp уходили в price_on_request
(полная таможня РФ требует и объём, и мощность). После бэкфилла карточки
пересчитываются следующим postgres_catalog_sync (needs_pricing_recompute=TRUE).

Примеры:
    python backend/scripts/backfill_usa_power.py --dsn "$DATABASE_URL"
    python backend/scripts/backfill_usa_power.py --dsn "$DATABASE_URL" --no-vin --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import psycopg2
import psycopg2.extras

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from us_power import fill_usa_power, flush_vin_cache  # noqa: E402

DEFAULT_SOURCE = "autotrader"


def _dsn(args_dsn: str) -> str:
    return (args_dsn or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN") or "").strip()


def _parse_hp(data: Dict[str, Any]) -> Optional[int]:
    for key in ("power", "power_hp", "hp"):
        v = data.get(key)
        if v is None or str(v).strip() == "":
            continue
        digits = "".join(ch for ch in str(v) if ch.isdigit())
        if digits:
            hp = int(digits)
            if 20 <= hp <= 2500:
                return hp
    return None


def _select_batch(cur: Any, args: argparse.Namespace, last_id: int, limit: int) -> list:
    params: list[Any] = [last_id]
    where_source = ""
    if args.source and args.source != "*":
        where_source = "AND source = %s"
        params.append(args.source)
    params.append(limit)
    cur.execute(
        f"""
        SELECT id, data, power_hp
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
    return cur.fetchall()


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill USA (Autotrader) power_hp from vPIC/us_engine_map")
    p.add_argument("--dsn", default="", help="PostgreSQL DSN (или DATABASE_URL/WRA_PG_DSN)")
    p.add_argument("--source", default=DEFAULT_SOURCE, help="cars.source filter ('*' = все)")
    p.add_argument("--batch-size", type=int, default=500, help="Размер батча")
    p.add_argument("--max-rows", type=int, default=0, help="Ограничить число строк (0 = все)")
    p.add_argument("--no-vin", action="store_true", help="Не ходить в NHTSA vPIC (только us_engine_map)")
    p.add_argument("--dry-run", action="store_true", help="Ничего не писать в БД, только отчёт")
    args = p.parse_args()

    dsn = _dsn(args.dsn)
    if not dsn:
        print("PostgreSQL DSN is required: --dsn или DATABASE_URL/WRA_PG_DSN")
        return 2

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    processed = updated = skipped = 0
    by_layer: Dict[str, int] = {}
    last_id = 0

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            while True:
                if args.max_rows > 0 and processed >= args.max_rows:
                    break
                limit = args.batch_size
                if args.max_rows > 0:
                    limit = min(limit, args.max_rows - processed)
                rows = _select_batch(cur, args, last_id, limit)
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
                    if payload.get("source") in (None, ""):
                        payload["source"] = args.source if args.source != "*" else "autotrader"

                    before = _parse_hp(payload)
                    found = fill_usa_power(payload, allow_vin=not args.no_vin)
                    after = _parse_hp(payload)
                    if not found or after is None or (before is not None and before == after):
                        skipped += 1
                        continue

                    layer = str(payload.get("power_source") or "unknown")
                    by_layer[layer] = by_layer.get(layer, 0) + 1

                    if args.dry_run:
                        updated += 1
                        continue

                    cur.execute(
                        """
                        UPDATE cars
                        SET data = %s,
                            power_hp = %s,
                            needs_pricing_recompute = TRUE,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (psycopg2.extras.Json(payload), int(after), rid),
                    )
                    updated += 1

                if not args.dry_run:
                    conn.commit()
                print(
                    f"progress processed={processed} updated={updated} skipped={skipped} last_id={last_id}",
                    flush=True,
                )
    finally:
        flush_vin_cache()
        conn.close()

    print(f"done processed={processed} updated={updated} skipped={skipped} layers={by_layer}", flush=True)
    if args.dry_run:
        print("dry-run: изменений в БД нет", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
