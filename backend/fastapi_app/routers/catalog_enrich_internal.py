"""Internal enrich: Postgres (если включён на сервере) без флагов в теле; LLM только если WRA_CATALOG_ENRICH_INTERNAL_LLM_FALLBACK=1."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response

from fastapi_app.config import get_settings
from fastapi_app.routers.catalog_enrich import (
    CatalogEnrichItem,
    CatalogEnrichResponse,
    execute_catalog_enrichment,
)

from pydantic import BaseModel, Field


router = APIRouter(tags=["internal"])


class InternalCatalogEnrichRequest(BaseModel):
    items: List[CatalogEnrichItem] = Field(..., min_length=1, max_length=48)


@router.post("/internal/catalog/enrich-terms", response_model=CatalogEnrichResponse)
async def internal_catalog_enrich_terms(
    request: Request,
    response: Response,
    body: InternalCatalogEnrichRequest,
    x_wra_admin_key: Optional[str] = Header(None, alias="X-WRA-Admin-Key"),
) -> CatalogEnrichResponse:
    """
    То же самое enrich, но:
    - **авто-PG**, если на сервере `WRA_CATALOG_ENRICH_PG_CACHE_ENABLED=1`;
    - **авто-LLM** только если `WRA_CATALOG_ENRICH_INTERNAL_LLM_FALLBACK=1` и глобальный LLM настроен;
    - авторизация: `X-WRA-Admin-Key` = `WRA_CACHE_INVALIDATE_SECRET`;
    - rate limit общего enrich к этому пути не применяется.
    """
    settings = get_settings()
    secret = (settings.cache_invalidate_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="internal_admin_disabled")
    if (x_wra_admin_key or "").strip() != secret:
        raise HTTPException(status_code=401, detail="unauthorized")

    if not settings.catalog_enrich_enabled:
        raise HTTPException(status_code=404, detail="catalog enrich disabled")

    use_pg = bool(settings.catalog_enrich_pg_cache_enabled)
    use_llm = bool(
        settings.catalog_enrich_internal_llm_fallback and settings.catalog_enrich_llm_fallback
    )

    resp, etag = await execute_catalog_enrichment(
        request=request,
        items=list(body.items),
        settings=settings,
        use_pg_term_cache=use_pg,
        use_llm_fallback=use_llm,
        catalog_header_for_rate_limit=None,
        apply_rate_limit=False,
    )
    if etag:
        response.headers["ETag"] = etag
    return resp
