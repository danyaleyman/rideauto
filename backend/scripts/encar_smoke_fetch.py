#!/usr/bin/env python3
"""
Лёгкий smoke Encar API без PostgreSQL:
- fetch list page
- fetch detail + extras
- normalize через EncarFullParser
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from encar_scraper import load_config  # noqa: E402
from parser_full import EncarFullParser  # noqa: E402
from scraper_pipeline.encar.client import AsyncEncarClient  # noqa: E402
from scraper_pipeline.encar.parser import parse_one_car_async  # noqa: E402


async def _pick_list_items(
    client: AsyncEncarClient,
    *,
    car_types: list[str],
    limit: int,
    page_size: int,
) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for car_type in car_types:
        data, status, _err = await client.fetch_list_page(0, page_size, car_type)
        if status != 200 or not isinstance(data, dict):
            continue
        for item in (data.get("SearchResults") or []):
            if len(out) >= limit:
                break
            if not isinstance(item, dict):
                continue
            car_id = str(item.get("Id") or "").strip()
            if not car_id or car_id in seen:
                continue
            seen.add(car_id)
            out.append((car_type, item))
        if len(out) >= limit:
            break
    return out


async def _amain(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger("encar_smoke")
    config = load_config(str(Path(args.config).expanduser().resolve()))
    limit = max(1, min(20, int(args.limit)))
    page_size = max(limit, 20)
    parser = EncarFullParser()
    rows: List[Dict[str, Any]] = []

    car_types = [str(x).strip() for x in (args.car_type or []) if str(x).strip()] or ["for", "kor"]
    async with AsyncEncarClient(config, log) as client:
        picked = await _pick_list_items(client, car_types=car_types, limit=limit, page_size=page_size)
        if not picked:
            print("No list items fetched from Encar API", file=sys.stderr)
            return 5

        for car_type, item in picked:
            car_id = str(item.get("Id") or "").strip()
            detail, d_status, d_err = await client.fetch_vehicle_detail(car_id)
            if d_status != 200 or not isinstance(detail, dict):
                rows.append(
                    {
                        "car_id": car_id,
                        "car_type": car_type,
                        "status": "detail_fail",
                        "http_detail": d_status,
                        "err_detail": d_err,
                    }
                )
                continue
            plate = detail.get("vehicleNo")
            seller_id = None
            sep_item = detail.get("item")
            if isinstance(sep_item, list) and sep_item:
                sep_item = sep_item[0]
            if isinstance(sep_item, dict) and sep_item.get("Separation"):
                seller_id = (sep_item.get("Separation") or [None])[0]
            if not seller_id and item.get("Separation"):
                seller_id = (item.get("Separation") or [None])[0]

            record, s_record, _ = await client.fetch_record(car_id, str(plate or "").strip()) if plate else (None, 0, "no plate")
            diagnosis, s_diag, _ = await client.fetch_diagnosis(car_id)
            inspection, s_insp, _ = await client.fetch_inspection(car_id)
            sellingpoint, s_sell, _ = await client.fetch_sellingpoint(car_id)
            user_info, s_user, _ = await client.fetch_user(str(seller_id or "").strip()) if seller_id else (None, 0, "no seller_id")

            normalized = await parse_one_car_async(
                parser,
                car_id,
                item,
                detail,
                diagnosis if isinstance(diagnosis, dict) else None,
                record if isinstance(record, dict) else None,
                inspection if isinstance(inspection, dict) else None,
                sellingpoint if isinstance(sellingpoint, dict) else None,
                user_info if isinstance(user_info, dict) else None,
                source_meta=None,
            )
            data = (normalized or {}).get("data") if isinstance(normalized, dict) else {}
            images = data.get("images") if isinstance(data, dict) else []
            image_count = len(images) if isinstance(images, list) else 0
            rows.append(
                {
                    "car_id": car_id,
                    "car_type": car_type,
                    "status": "ok" if normalized else "parse_fail",
                    "http_detail": d_status,
                    "http_record": s_record,
                    "http_diagnosis": s_diag,
                    "http_inspection": s_insp,
                    "http_sellingpoint": s_sell,
                    "http_user": s_user,
                    "image_count": image_count,
                    "mark": data.get("mark") if isinstance(data, dict) else None,
                    "model": data.get("model") if isinstance(data, dict) else None,
                }
            )

    print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--car-type", action="append", default=[], help="for/kor, can pass multiple")
    args = p.parse_args()
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
