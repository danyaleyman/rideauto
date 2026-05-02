#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import requests

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from catalog_encar_pricing import encar_tier_for_pricing_snapshot, sync_pricing_clean_block
from catalog_listing_price import clear_estimated_price_fields, encar_has_list_price
from clean_layers import build_clean_layers
from encar_price_intent import classify_encar_price_intent, price_signals_json


def _postgres_dsn(config_path: Path) -> str:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml and config_path.is_file():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            dsn = str((((cfg.get("storage") or {}).get("postgres") or {}).get("dsn") or "")).strip()
            if dsn:
                return dsn
        except Exception:
            pass
    return (os.environ.get("DATABASE_URL") or "").strip()


def _fetch_candidates(dsn: str, *, limit: int, car_ids: Sequence[str] | None = None) -> List[Tuple[int, str, Dict[str, Any]]]:
    import psycopg2
    import psycopg2.extras

    if car_ids:
        q = """
        SELECT id, car_id, data
        FROM cars
        WHERE source='encar'
          AND car_id = ANY(%s)
        ORDER BY updated_at DESC
        """
        params = (list(car_ids),)
    else:
        q = """
        SELECT id, car_id, data
        FROM cars
        WHERE source='encar'
          AND (encar_listing_sold = false OR encar_listing_sold IS NULL)
        ORDER BY updated_at DESC
        LIMIT %s
        """
        params = (limit,)
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, params)
            out: List[Tuple[int, str, Dict[str, Any]]] = []
            for r in cur.fetchall():
                data = r.get("data")
                if not isinstance(data, dict):
                    continue
                out.append((int(r["id"]), str(r["car_id"]), data))
            return out


def _fetch_detail_html(car_id: str, timeout_sec: float) -> str:
    url = f"https://fem.encar.com/cars/detail/{car_id}?carid={car_id}"
    r = requests.get(
        url,
        timeout=timeout_sec,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; WRA-PriceIntentWorker/1.0)",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        },
    )
    if r.status_code != 200:
        return ""
    return r.text or ""


def _update_row(
    dsn: str,
    *,
    row_id: int,
    data: Dict[str, Any],
    intent: str,
    signals: List[str],
    dry_run: bool,
) -> None:
    if dry_run:
        return
    import psycopg2
    import psycopg2.extras

    next_data = dict(data)
    next_data["price_intent"] = intent
    next_data["price_intent_confidence"] = "high" if signals else "low"
    next_data["price_signals"] = price_signals_json(signals)
    next_data["price_classifier_version"] = "v1-live"
    if intent in ("monthly_finance", "reserved_placeholder"):
        next_data["price_on_request"] = True
        next_data["encar_listing_reserved"] = (intent == "reserved_placeholder")
        next_data.pop("my_price", None)
        next_data["pricing_tier"] = "price_on_request"
        clear_estimated_price_fields(next_data)
        price_rub = None
    else:
        next_data.pop("encar_listing_reserved", None)
        if next_data.get("price_on_request") is True:
            next_data.pop("price_on_request", None)
        price_rub = data.get("my_price")
        if encar_has_list_price(next_data):
            snap = encar_tier_for_pricing_snapshot(next_data)
            next_data["pricing_tier"] = snap
            if snap == "price_on_request":
                next_data["price_on_request"] = True
                clear_estimated_price_fields(next_data)
                price_rub = None
            else:
                next_data.pop("price_on_request", None)
        else:
            next_data["pricing_tier"] = "price_on_request"
            next_data["price_on_request"] = True
            clear_estimated_price_fields(next_data)
            price_rub = None

    fresh = build_clean_layers(next_data)
    for key in (
        "clean_schema_version",
        "identity_clean",
        "spec_clean",
        "condition_clean",
        "seller_clean",
        "media_clean",
    ):
        next_data[key] = fresh[key]
    next_data["pricing_clean"] = fresh["pricing_clean"]
    sync_pricing_clean_block(next_data)

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cars
                SET data=%s::jsonb,
                    price_rub=COALESCE(%s, price_rub),
                    needs_pricing_recompute = TRUE,
                    updated_at=now()
                WHERE id=%s
                """,
                (json.dumps(next_data, ensure_ascii=False), price_rub, row_id),
            )
        conn.commit()


def run_once(
    dsn: str,
    *,
    limit: int,
    timeout_sec: float,
    delay_min: float,
    delay_max: float,
    dry_run: bool,
    car_ids: Sequence[str] | None = None,
) -> Dict[str, int]:
    rows = _fetch_candidates(dsn, limit=limit, car_ids=car_ids)
    stats = {"checked": 0, "monthly": 0, "reserved": 0, "sale": 0, "unknown": 0, "updated": 0}
    for row_id, car_id, data in rows:
        html = _fetch_detail_html(car_id, timeout_sec=timeout_sec)
        intent, signals = classify_encar_price_intent(data, extra_texts=[html] if html else None)
        stats["checked"] += 1
        if intent in stats:
            stats[intent] += 1
        _update_row(dsn, row_id=row_id, data=data, intent=intent, signals=signals, dry_run=dry_run)
        if not dry_run:
            stats["updated"] += 1
        time.sleep(random.uniform(delay_min, delay_max))
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description="Encar live price-intent worker")
    p.add_argument("--config", default="scraper_config.yaml")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--timeout-sec", type=float, default=10.0)
    p.add_argument("--delay-min", type=float, default=0.2)
    p.add_argument("--delay-max", type=float, default=0.7)
    p.add_argument("--once", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--car-id", action="append", default=[], help="Specific Encar car_id (can pass multiple)")
    args = p.parse_args()

    dsn = _postgres_dsn(Path(args.config).expanduser().resolve())
    if not dsn:
        raise SystemExit("DATABASE_URL/storage.postgres.dsn is empty")

    stats = run_once(
        dsn,
        limit=max(1, min(args.limit, 2000)),
        timeout_sec=max(2.0, min(args.timeout_sec, 30.0)),
        delay_min=max(0.0, args.delay_min),
        delay_max=max(max(0.0, args.delay_min), args.delay_max),
        dry_run=args.dry_run,
        car_ids=[str(x).strip() for x in (args.car_id or []) if str(x).strip()] or None,
    )
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()

