"""Sitemap refs для SEO (B2C)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query, Request

router = APIRouter(tags=["seo"])


@router.get("/sitemap/cars")
async def sitemap_cars(
    request: Request,
    limit: int = Query(default=5000, ge=1, le=20000),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Последние car_id + updated_at для dynamic sitemap (indexable only)."""
    pool = request.app.state.pg_pool
    total = await pool.fetchval(
        """
        SELECT COUNT(*)::int FROM cars
        WHERE dedupe_canonical_car_id IS NULL
          AND COALESCE(encar_listing_sold, false) = false
          AND COALESCE(che168_listing_sold, false) = false
        """
    )
    rows = await pool.fetch(
        """
        SELECT car_id, updated_at
        FROM cars
        WHERE dedupe_canonical_car_id IS NULL
          AND COALESCE(encar_listing_sold, false) = false
          AND COALESCE(che168_listing_sold, false) = false
        ORDER BY updated_at DESC NULLS LAST
        LIMIT $1 OFFSET $2
        """,
        int(limit),
        int(offset),
    )
    items = [
        {
            "ref": str(r["car_id"]),
            "updated_at": r["updated_at"].isoformat().replace("+00:00", "Z")
            if r["updated_at"]
            else None,
        }
        for r in rows
    ]
    return {"result": items, "limit": limit, "offset": offset, "total": int(total or 0)}
