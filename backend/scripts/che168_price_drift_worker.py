#!/usr/bin/env python3
"""
Сверка цены Che168 (GET carinfo) с cars.data — при дрейфе обновляет JSON и needs_pricing_recompute.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from che168_scraper import setup_logging as che168_setup_logging  # noqa: E402
from encar_scraper import load_config  # noqa: E402
from pricechina import parse_price_cny  # noqa: E402
from scraper_pipeline.che168.client import AsyncChe168Client  # noqa: E402
from scraper_pipeline.che168.workers import che168_carinfo_body  # noqa: E402


def _dsn(config: dict) -> str:
    s = (config.get("storage") or {}).get("postgres") or {}
    dsn = str(s.get("dsn") or "").strip()
    if dsn:
        return dsn
    return (os.environ.get("DATABASE_URL") or "").strip()


def _to_infoid(car_id: str) -> str:
    s = str(car_id or "").strip()
    if s.lower().startswith("che168-"):
        return s.split("-", 1)[-1]
    return s


def _inner_card(payload: Dict[str, Any]) -> Dict[str, Any]:
    d = payload.get("data")
    return d if isinstance(d, dict) else payload


def _numeric_cny(card: Dict[str, Any]) -> float:
    return float(parse_price_cny(card) or 0.0)


async def _run_batch(
    *,
    client: AsyncChe168Client,
    rows: List[Tuple[int, str, Dict[str, Any]]],
    dsn: str,
    rel_tol: float,
    abs_tol: float,
    delay_min: float,
    delay_max: float,
) -> Tuple[int, int, int]:
    import psycopg2

    updated = unchanged = skip = 0
    for row_id, car_id, payload in rows:
        if not isinstance(payload, dict):
            skip += 1
            continue
        card = _inner_card(payload)
        if not isinstance(card, dict):
            skip += 1
            continue
        old_cny = _numeric_cny(card)
        infoid = _to_infoid(car_id)
        raw, st, _err = await client.fetch_carinfo(infoid)
        if int(st) != 200 or not isinstance(raw, dict):
            skip += 1
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            continue
        body = che168_carinfo_body(raw)
        live_f = float(parse_price_cny({"price_cny": body.get("price")}) or 0.0)
        if live_f <= 0:
            skip += 1
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            continue
        diff = abs(live_f - old_cny)
        if old_cny > 0 and diff <= max(abs_tol, old_cny * rel_tol):
            unchanged += 1
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            continue

        card["price_cny"] = live_f
        card["che168_price_drift_checked_at"] = datetime.now(timezone.utc).isoformat()
        if isinstance(payload.get("data"), dict):
            payload["data"] = card

        try:
            with psycopg2.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE cars
                        SET data = %s::jsonb,
                            needs_pricing_recompute = TRUE,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (json.dumps(payload, ensure_ascii=False), row_id),
                    )
                conn.commit()
        except Exception:
            skip += 1
        else:
            updated += 1
        await asyncio.sleep(random.uniform(delay_min, delay_max))
    return updated, unchanged, skip


def _fetch_batch(
    dsn: str, *, limit: int, min_age_hours: float, car_ids: Optional[List[str]]
) -> List[Tuple[int, str, Dict[str, Any]]]:
    import psycopg2
    import psycopg2.extras

    out: List[Tuple[int, str, Dict[str, Any]]] = []
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if car_ids:
                cur.execute(
                    """
                    SELECT id, car_id, data
                    FROM cars
                    WHERE lower(trim(source)) = 'che168'
                      AND car_id = ANY(%s)
                    ORDER BY id ASC
                    """,
                    (list(car_ids),),
                )
            else:
                cur.execute(
                    """
                    SELECT id, car_id, data
                    FROM cars
                    WHERE lower(trim(source)) = 'che168'
                      AND COALESCE(che168_listing_sold, false) = false
                      AND updated_at < (now() - (%s * interval '1 hour'))
                    ORDER BY updated_at ASC
                    LIMIT %s
                    """,
                    (min_age_hours, limit),
                )
            for r in cur.fetchall():
                d = r.get("data")
                if isinstance(d, str):
                    try:
                        d = json.loads(d)
                    except Exception:
                        continue
                if not isinstance(d, dict):
                    continue
                out.append((int(r["id"]), str(r["car_id"]), d))
    return out


async def amain() -> int:
    p = argparse.ArgumentParser(description="Che168 price drift vs carinfo API")
    p.add_argument("--config", default="che168_scraper.yaml")
    p.add_argument("--limit", type=int, default=80)
    p.add_argument("--min-age-hours", type=float, default=6.0)
    p.add_argument("--rel-tol", type=float, default=0.002)
    p.add_argument("--abs-tol", type=float, default=50.0)
    p.add_argument("--delay-min", type=float, default=0.35)
    p.add_argument("--delay-max", type=float, default=1.0)
    p.add_argument("--car-id", action="append", default=[])
    args = p.parse_args()

    cfg_path = Path(args.config).expanduser().resolve()
    config = load_config(str(cfg_path))
    log = che168_setup_logging(config)
    _dev = (os.environ.get("CHE168_DEVICE_ID") or os.environ.get("CHE168_DEVICEID") or "").strip()
    if _dev:
        config.setdefault("che168", {})["deviceid"] = _dev

    dsn = _dsn(config)
    if not dsn:
        log.error("Нет DSN")
        return 2

    cids = [str(x).strip() for x in args.car_id if str(x).strip()]
    rows = _fetch_batch(
        dsn,
        limit=max(1, args.limit),
        min_age_hours=max(0.0, float(args.min_age_hours)),
        car_ids=cids or None,
    )
    log.info("che168_price_drift: candidates=%s", len(rows))
    if not rows:
        print(json.dumps({"updated": 0, "unchanged": 0, "skip": 0}, ensure_ascii=False))
        return 0

    async with AsyncChe168Client(config, log) as client:
        u, n, k = await _run_batch(
            client=client,
            rows=rows,
            dsn=dsn,
            rel_tol=float(args.rel_tol),
            abs_tol=float(args.abs_tol),
            delay_min=float(args.delay_min),
            delay_max=float(args.delay_max),
        )
    print(json.dumps({"updated": u, "unchanged": n, "skip": k}, ensure_ascii=False))
    return 0


def main() -> None:
    try:
        rc = asyncio.run(amain())
    except KeyboardInterrupt:
        rc = 130
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
