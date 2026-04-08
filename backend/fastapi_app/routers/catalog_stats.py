"""Статистика каталога (Postgres): свежие записи по рынку."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from fastapi_app.cached_route import serve_cached_json
from fastapi_app.schemas.api import CatalogDailyAdditionsResponse

router = APIRouter(tags=["catalog"])

# Совпадает с ночными systemd-таймерами и фильтром Meilisearch (Корея / Китай).
_TZ = "Asia/Yekaterinburg"


@router.get("/catalog/daily-additions", response_model=CatalogDailyAdditionsResponse)
async def catalog_daily_additions(request: Request, region: str) -> CatalogDailyAdditionsResponse:
    reg = (region or "").strip().lower()
    if reg == "korea":
        source = "encar"
    elif reg == "china":
        source = "dongchedi"
    else:
        raise HTTPException(
            status_code=400,
            detail="region must be korea or china",
        )

    flat = {"region": reg}

    async def compute() -> dict:
        pool: asyncpg.Pool = request.app.state.pg_pool
        row = await pool.fetchrow(
            f"""
            SELECT
              COUNT(*)::bigint AS n,
              ((now() AT TIME ZONE '{_TZ}')::date)::text AS local_date
            FROM cars
            WHERE source = $1
              AND (created_at AT TIME ZONE '{_TZ}')::date
                  = ((now() AT TIME ZONE '{_TZ}')::date)
            """,
            source,
        )
        n = int(row["n"]) if row and row["n"] is not None else 0
        d = str(row["local_date"]) if row and row["local_date"] is not None else ""
        return {
            "count": n,
            "region": reg,
            "local_date": d,
            "timezone": _TZ,
        }

    data = await serve_cached_json(
        request,
        segment="catalog_daily_additions",
        ttl_sec=120,
        flat=flat,
        compute=compute,
    )
    return CatalogDailyAdditionsResponse.model_validate(data)
