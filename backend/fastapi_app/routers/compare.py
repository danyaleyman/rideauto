"""Сравнение до 4 автомобилей (B2C)."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Request

from fastapi_app.config import get_settings
from fastapi_app.pg_catalog import fetch_cars_by_ids
from fastapi_app.rate_limit import public_rate_limit
from read_models import build_catalog_read_model

router = APIRouter(tags=["catalog"])

_MAX_COMPARE = 4


def _compare_row(car: Dict[str, Any], car_id: str) -> Dict[str, Any]:
    rm = build_catalog_read_model(
        car,
        use_clean=True,
        api_version=str(get_settings().api_contract_version or "v1"),
    )
    data = rm.get("data") if isinstance(rm.get("data"), dict) else {}
    images = data.get("images") or data.get("image_urls") or []
    thumb = images[0] if isinstance(images, list) and images else None
    title = " ".join(x for x in [data.get("mark"), data.get("model")] if x).strip() or car_id
    return {
        "id": car_id,
        "title": title,
        "mark": data.get("mark"),
        "model": data.get("model"),
        "year": data.get("year") or data.get("year_month"),
        "mileage_km": data.get("mileage_km") or data.get("mileage"),
        "price_rub": data.get("price_rub") or data.get("rub_price"),
        "fuel": data.get("fuel") or data.get("fuel_type"),
        "transmission": data.get("transmission") or data.get("transmission_type"),
        "power_hp": data.get("power_hp"),
        "body_type": data.get("body_type"),
        "drive_type": data.get("drive_type"),
        "source": data.get("source"),
        "thumb_url": thumb,
        "url_path": f"/car/{car_id}",
    }


@router.get("/compare")
@public_rate_limit()
async def compare_cars(
    request: Request,
    ids: str = Query(..., description="До 4 car_id через запятую"),
) -> Dict[str, Any]:
    raw = [x.strip() for x in (ids or "").split(",") if x.strip()]
    if not raw:
        raise HTTPException(status_code=400, detail="ids required")
    if len(raw) > _MAX_COMPARE:
        raise HTTPException(status_code=400, detail=f"max {_MAX_COMPARE} ids")
    # preserve order, dedupe
    ordered: List[str] = []
    seen: set[str] = set()
    for cid in raw:
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)
    pool = request.app.state.pg_pool
    by_id = await fetch_cars_by_ids(pool, ordered)
    result = []
    for cid in ordered:
        car = by_id.get(cid)
        if car:
            result.append(_compare_row(car, cid))
    return {"result": result}
