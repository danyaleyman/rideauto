from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from fastapi_app.cached_route import serve_cached_json
from fastapi_app.config import get_settings
from fastapi_app.pg_catalog import fetch_car_any_id
from fastapi_app.schemas.api import CarDetailResponse

router = APIRouter(tags=["car"])


@router.get("/car/{car_ref}", response_model=CarDetailResponse)
async def get_car(car_ref: str, request: Request) -> Dict[str, Any]:
    settings = get_settings()
    pool = request.app.state.pg_pool
    qp = list(request.query_params.multi_items())
    flat = tuple(sorted(qp + [("__car_ref__", car_ref)]))

    async def compute() -> Dict[str, Any]:
        row = await fetch_car_any_id(pool, car_ref)
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        return CarDetailResponse(result=row).model_dump()

    try:
        return await serve_cached_json(
            request,
            segment="car",
            ttl_sec=settings.cache_ttl_car_sec,
            flat=flat,
            compute=compute,
        )
    except HTTPException:
        raise
