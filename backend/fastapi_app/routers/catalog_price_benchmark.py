"""GET /api/catalog/price-benchmark — медиана и коридор цен по похожим объявлениям."""

from __future__ import annotations

from typing import Any, Dict, Optional

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from fastapi_app.cached_route import serve_cached_json
from fastapi_app.catalog_price_benchmark import (
    catalog_benchmark_eligible,
    compute_price_benchmark,
)
from fastapi_app.pg_catalog import fetch_car_any_id
from fastapi_app.schemas.api import PriceBenchmarkResponse

router = APIRouter(tags=["catalog"])


def _flat_query(request: Request) -> Dict[str, str]:
    return {k: str(v) for k, v in request.query_params.multi_items()}


def _empty_response() -> PriceBenchmarkResponse:
    return PriceBenchmarkResponse(
        cohort={},
        peer_all=None,
        peer_clean=None,
        listing=None,
        eligible=False,
    )


@router.get("/catalog/price-benchmark", response_model=PriceBenchmarkResponse)
async def catalog_price_benchmark(
    request: Request,
    car_id: Optional[str] = None,
) -> PriceBenchmarkResponse:
    flat = _flat_query(request)
    pool: asyncpg.Pool = request.app.state.pg_pool
    ref = (car_id or flat.get("car_id") or "").strip()

    if not ref and not catalog_benchmark_eligible(flat):
        return _empty_response()

    listing_row: Optional[asyncpg.Record] = None
    listing_price: Optional[float] = None

    if ref:
        car = await fetch_car_any_id(pool, ref)
        if not car:
            raise HTTPException(status_code=404, detail="car not found")
        cid = str(car.get("id") or ref)
        listing_row = await pool.fetchrow(
            """
            SELECT mark, model, encar_model_group, source, year, year_month, mileage_km, price_rub
            FROM cars
            WHERE car_id = $1
            LIMIT 1
            """,
            cid,
        )
        if listing_row is None:
            raise HTTPException(status_code=404, detail="car not found")
        pr = listing_row.get("price_rub")
        if pr is not None:
            try:
                fv = float(pr)
                if fv > 0:
                    listing_price = fv
            except (TypeError, ValueError):
                pass
        if not catalog_benchmark_eligible(flat) and not str(listing_row.get("mark") or "").strip():
            return _empty_response()

    cache_flat = dict(flat)
    if ref:
        cache_flat["car_id"] = ref

    async def compute() -> Dict[str, Any]:
        body = await compute_price_benchmark(
            pool,
            flat,
            listing_row=listing_row,
            listing_price_rub=listing_price,
        )
        body["eligible"] = True
        return body

    data = await serve_cached_json(
        request,
        segment="catalog_price_benchmark",
        ttl_sec=300,
        flat=cache_flat,
        compute=compute,
    )
    return PriceBenchmarkResponse.model_validate(data)
