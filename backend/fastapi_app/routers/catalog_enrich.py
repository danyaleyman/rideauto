from __future__ import annotations

from typing import List

from fastapi import APIRouter, Header, HTTPException

from fastapi_app.catalog_enrich_llm import openai_enrich_missing
from fastapi_app.catalog_term_enrichment import enrich_batch, known_catalog_enrich_domains
from fastapi_app.config import get_settings

from pydantic import BaseModel, Field


router = APIRouter(tags=["catalog"])


class CatalogEnrichItem(BaseModel):
    text: str = Field(default="", max_length=2000, description="Исходная строка (часто KO с Encar).")
    domain: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Имя поля каталога: mark, engine_type/fuel, modelGroupName, …",
    )


class CatalogEnrichRequest(BaseModel):
    items: List[CatalogEnrichItem] = Field(..., min_length=1, max_length=48)
    use_llm_fallback: bool = Field(
        default=False,
        description="Если true и на сервере включён WRA_CATALOG_ENRICH_LLM_FALLBACK и задан ключ — "
        "дозаполнить пустой RU для KO/ZH через OpenAI (без Postgres).",
    )


class CatalogEnrichRow(BaseModel):
    text_in: str
    domain: str
    ru: str
    en: str
    source_ru: str


class CatalogEnrichResponse(BaseModel):
    result: List[CatalogEnrichRow]
    llm_fallback_used: bool = Field(default=False, description="Был ли применён LLM-дозаполнитель")


def _check_access(header_key: str | None) -> None:
    settings = get_settings()
    if not settings.catalog_enrich_enabled:
        raise HTTPException(status_code=404, detail="catalog enrich disabled")
    secret = (settings.catalog_enrich_secret or "").strip()
    if not secret:
        return
    if (header_key or "").strip() != secret:
        raise HTTPException(status_code=403, detail="invalid enrich key")


ALLOWED_PREVIEW = sorted(known_catalog_enrich_domains())


@router.post("/catalog/enrich-terms", response_model=CatalogEnrichResponse)
async def catalog_enrich_terms(
    payload: CatalogEnrichRequest,
    x_wra_catalog_enrich_key: str | None = Header(None, alias="X-WRA-Catalog-Enrich-Key"),
) -> CatalogEnrichResponse:
    """
    KO/EN «сырой» текст фасета/карточки → дополнительные **RU** и канонический **EN** (статические мапы + при необходимости LLM).

    По умолчанию только статика (`korea_static` / facet fuel), без нагрузки на БД.
    Опционально: `use_llm_fallback=true` при `WRA_CATALOG_ENRICH_LLM_FALLBACK=1` и ключе
    (`OPENAI_API_KEY` или `WRA_TRANSLATE_API_KEY`).

    Если задан `WRA_CATALOG_ENRICH_SECRET`, передайте тот же токен в заголовке `X-WRA-Catalog-Enrich-Key`.
    """
    _check_access(x_wra_catalog_enrich_key)
    allowed = known_catalog_enrich_domains()
    for it in payload.items:
        dom = (it.domain or "").strip()
        if dom not in allowed:
            raise HTTPException(
                status_code=422,
                detail={"error": "unknown domain", "domain": dom, "allowed_sample": ALLOWED_PREVIEW[:24]},
            )
    settings = get_settings()
    rows = enrich_batch([(x.text.strip(), x.domain.strip()) for x in payload.items])
    llm_used = False
    if payload.use_llm_fallback:
        if not settings.catalog_enrich_llm_fallback:
            raise HTTPException(
                status_code=400,
                detail="LLM fallback is disabled on the server (set WRA_CATALOG_ENRICH_LLM_FALLBACK=1)",
            )
        if not (settings.translate_api_key or "").strip():
            raise HTTPException(
                status_code=503,
                detail="LLM fallback requested but no API key configured (OPENAI_API_KEY or WRA_TRANSLATE_API_KEY)",
            )
        rows, llm_used = await openai_enrich_missing(
            rows,
            settings=settings,
            max_llm_items=settings.catalog_enrich_llm_max_items,
        )
    return CatalogEnrichResponse(
        result=[CatalogEnrichRow(**r) for r in rows],
        llm_fallback_used=llm_used,
    )
