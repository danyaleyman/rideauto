from __future__ import annotations

import asyncio
from typing import Any, Dict

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from meilisearch import Client

from fastapi_app.cached_route import serve_cached_json
from fastapi_app.catalog_slim import slim_catalog_car
from fastapi_app.config import Settings, get_settings
from fastapi_app.cursor import decode_offset_cursor, encode_offset_cursor
from fastapi_app.meilisearch_query import build_meilisearch_filter, meilisearch_sort_list
from fastapi_app.pg_catalog import fetch_cars_by_ids
from fastapi_app.schemas.api import SearchMeta, SearchResponse

router = APIRouter(tags=["catalog"])


def _flat_query(request: Request) -> Dict[str, str]:
    return {str(k): str(v) for k, v in request.query_params.multi_items()}


async def _search_catalog(request: Request) -> SearchResponse:
    settings: Settings = get_settings()
    flat = _flat_query(request)
    try:
        limit = int(flat.get("per_page") or flat.get("limit") or "12")
    except ValueError:
        limit = 12
    limit = min(100, max(1, limit))
    sort = (flat.get("sort") or "date_new").strip()
    qtext = (flat.get("q") or flat.get("query") or "").strip()
    slim = (flat.get("full") or "").strip() != "1"
    offset = 0
    cur_raw = (flat.get("cursor") or "").strip()
    if cur_raw:
        decoded = decode_offset_cursor(cur_raw)
        if not decoded:
            raise HTTPException(status_code=400, detail="invalid cursor")
        off, lim_cur = decoded
        if lim_cur != limit:
            raise HTTPException(status_code=400, detail="cursor limit mismatch")
        offset = off

    pool: asyncpg.Pool = request.app.state.pg_pool
    meili: Client = request.app.state.meili
    idx = meili.index(settings.meilisearch_index)

    filt = build_meilisearch_filter(flat)
    opts: Dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "sort": meilisearch_sort_list(sort),
    }
    if filt:
        opts["filter"] = filt

    def _run_search():
        return idx.search(qtext, opts)

    ms = await asyncio.to_thread(_run_search)
    hits = ms.get("hits") or []
    car_ids = [str(h.get("id") or h.get("car_id") or "") for h in hits]
    car_ids = [x for x in car_ids if x]

    by_id = await fetch_cars_by_ids(pool, car_ids)
    result: list = []
    for cid in car_ids:
        car = by_id.get(cid)
        if not car:
            continue
        if slim:
            result.append(slim_catalog_car(car, cid))
        else:
            result.append(car)

    total = int(ms.get("estimatedTotalHits") or ms.get("totalHits") or 0)
    proc_ms = ms.get("processingTimeMs")
    if isinstance(proc_ms, float):
        proc_ms = int(proc_ms)

    next_cursor = None
    if car_ids and len(car_ids) == limit and offset + limit < total:
        next_cursor = encode_offset_cursor(offset + limit, limit)

    pages = max(1, (total + limit - 1) // limit) if total > 0 else 1
    cur_page = offset // limit + 1 if limit else 1
    next_page = cur_page + 1 if next_cursor and cur_page < pages else None

    meta = SearchMeta(
        total=total,
        limit=limit,
        per_page=limit,
        pages=pages,
        offset=offset,
        next_cursor=next_cursor,
        next_page=next_page,
        processing_time_ms=proc_ms,
        list_mode="slim" if slim else "full",
        sort=sort,
    )
    return SearchResponse(result=result, meta=meta)


async def _search_maybe_cached(request: Request) -> Dict[str, Any]:
    settings = get_settings()
    flat = _flat_query(request)

    async def compute() -> Dict[str, Any]:
        body = await _search_catalog(request)
        return body.model_dump()

    return await serve_cached_json(
        request,
        segment="search",
        ttl_sec=settings.cache_ttl_search_sec,
        flat=flat,
        compute=compute,
    )


@router.get("/search", response_model=SearchResponse)
async def search(request: Request) -> Dict[str, Any]:
    """Каталог через Meilisearch + гидратация карточек из PostgreSQL (как legacy `/api/cars`)."""
    return await _search_maybe_cached(request)


@router.get("/cars", response_model=SearchResponse)
async def cars_alias(request: Request) -> Dict[str, Any]:
    """Алиас для существующего фронта / nginx (`/api/cars`)."""
    return await _search_maybe_cached(request)
