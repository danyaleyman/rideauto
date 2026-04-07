"""Parser: нормализация ответов API через EncarFullParser (CPU-bound → executor)."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Optional

from parser_full import EncarFullParser


def parse_one_car_sync(
    parser: EncarFullParser,
    car_id: str,
    item: dict,
    detail: Optional[dict],
    diagnosis: Optional[dict],
    record: Optional[dict],
    inspection: Optional[dict],
    sellingpoint: Optional[dict],
    user_info: Optional[dict],
) -> Optional[dict]:
    try:
        inspection_structured = parser.parse_inspection(inspection, diagnosis) if (inspection or diagnosis) else {}
        photos = None
        if detail:
            photos = detail.get("photos") or []
        normalized = parser.normalize_car(
            car_id,
            item,
            detail,
            photos,
            diagnosis,
            inspection,
            sellingpoint,
            record,
            user_info,
            inspection_structured=inspection_structured,
        )
        normalized["id"] = car_id
        normalized["data"]["id"] = str(car_id)
        return normalized
    except Exception:
        return None


async def parse_one_car_async(
    parser: EncarFullParser,
    car_id: str,
    item: dict,
    detail: Optional[dict],
    diagnosis: Optional[dict],
    record: Optional[dict],
    inspection: Optional[dict],
    sellingpoint: Optional[dict],
    user_info: Optional[dict],
) -> Optional[dict]:
    loop = asyncio.get_running_loop()
    fn = partial(
        parse_one_car_sync,
        parser,
        car_id,
        item,
        detail,
        diagnosis,
        record,
        inspection,
        sellingpoint,
        user_info,
    )
    return await loop.run_in_executor(None, fn)
