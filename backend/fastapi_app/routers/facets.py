from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from meilisearch import Client

from fastapi_app.cached_route import serve_cached_json
from fastapi_app.config import Settings, get_settings
from fastapi_app.meilisearch_query import (
    FACET_SPECS_MEILI,
    build_meilisearch_filter,
    facet_distribution_to_rows,
)
from fastapi_app.schemas.api import FacetsResponse

router = APIRouter(tags=["facets"])
logger = logging.getLogger(__name__)


def _flat_query(request: Request) -> Dict[str, str]:
    return {str(k): str(v) for k, v in request.query_params.multi_items()}


async def _facet_dimension(
    meili: Client,
    index_name: str,
    flat: Dict[str, str],
    omit_keys: frozenset,
    meili_attr: str,
) -> list:
    filt = build_meilisearch_filter(flat, omit_keys=omit_keys)
    idx = meili.index(index_name)
    opts: Dict[str, Any] = {"limit": 0, "facets": [meili_attr]}
    if filt:
        opts["filter"] = filt

    def _run():
        return idx.search("", opts)

    res = await asyncio.to_thread(_run)
    dist = (res.get("facetDistribution") or {}).get(meili_attr) or {}
    return facet_distribution_to_rows(dist, attr=meili_attr, query_flat=flat)


async def _facets_body(request: Request) -> Dict[str, Any]:
    settings: Settings = get_settings()
    flat = _flat_query(request)
    meili: Client = request.app.state.meili

    tasks = [
        _facet_dimension(meili, settings.meilisearch_index, flat, omit, attr)
        for _, omit, attr in FACET_SPECS_MEILI
    ]
    raw: List[Any] = await asyncio.gather(*tasks, return_exceptions=True)
    parts: list = []
    for i, r in enumerate(raw):
        if isinstance(r, BaseException):
            meili_attr = FACET_SPECS_MEILI[i][2] if i < len(FACET_SPECS_MEILI) else "?"
            logger.error("facet dimension failed meili_attr=%s", meili_attr, exc_info=r)
            parts.append([])
        else:
            parts.append(r)
    keys = [spec[0] for spec in FACET_SPECS_MEILI]
    payload = dict(zip(keys, parts))
    payload["api_version"] = str(settings.api_contract_version or "v1")
    return FacetsResponse(**payload).model_dump()


async def _facets_cached(request: Request) -> Dict[str, Any]:
    settings = get_settings()
    flat = _flat_query(request)

    async def compute() -> Dict[str, Any]:
        return await _facets_body(request)

    return await serve_cached_json(
        request,
        segment="facets",
        ttl_sec=settings.cache_ttl_facets_sec,
        flat=flat,
        compute=compute,
    )


@router.get("/facets", response_model=FacetsResponse)
async def facets(request: Request) -> Dict[str, Any]:
    """Фасеты каталога через Meilisearch (omit-паттерн query-параметров)."""
    return await _facets_cached(request)


@router.get("/filters", response_model=FacetsResponse)
async def filters_alias(request: Request) -> Dict[str, Any]:
    return await _facets_cached(request)
