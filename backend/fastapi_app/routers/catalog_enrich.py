from __future__ import annotations

import hashlib
import json
from typing import List, Optional, Tuple

from fastapi import APIRouter, Header, HTTPException, Request, Response

from fastapi_app.catalog_enrich_llm import openai_enrich_missing
from fastapi_app.catalog_enrich_pg import enrich_rows_pg_term_cache
from fastapi_app.catalog_enrich_rate_limit import (
    enrich_rate_identity,
    enforce_catalog_enrich_rate_limit,
)
from fastapi_app.catalog_term_enrichment import enrich_batch, known_catalog_enrich_domains
from fastapi_app.config import Settings, get_settings

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
    use_pg_term_cache: bool = Field(
        default=False,
        description="Если true и WRA_CATALOG_ENRICH_PG_CACHE_ENABLED=1 — batched SELECT в term_translation_cache (read-only).",
    )
    use_llm_fallback: bool = Field(
        default=False,
        description="Если true и на сервере включён WRA_CATALOG_ENRICH_LLM_FALLBACK и задан ключ — "
        "дозаполнить пустой RU для KO/ZH через OpenAI (без записи в Postgres).",
    )


class CatalogEnrichRow(BaseModel):
    text_in: str
    domain: str
    ru: str
    en: str
    source_ru: str


class CatalogEnrichResponse(BaseModel):
    result: List[CatalogEnrichRow]
    pg_cache_hits_ru: int = Field(default=0, description="RU из Postgres term_translation_cache (SELECT)")
    pg_cache_hits_en: int = Field(default=0, description="EN из того же кэша")
    pg_cache_keys_queried: int = Field(default=0, description="Число пар во всех UNNEST этого запроса")
    pg_truncated: bool = Field(
        default=False,
        description="True если ключей было больше, чем уместилось за раунды (см. WRA_CATALOG_ENRICH_PG_MAX_*).",
    )
    pg_cache_rounds: int = Field(default=0, description="Сколько раундов UNNEST реально выполнено")
    llm_fallback_used: bool = Field(default=False, description="Был ли хотя бы один RU через LLM‑кэш/API")
    llm_candidates: int = Field(default=0, description="Строк KO/ZH с пустым RU до шага LLM")
    llm_memory_cache_hits: int = Field(default=0, description="Подставлено из LRU процесса")
    llm_redis_cache_hits: int = Field(default=0, description="Подставлено из Redis KV")
    llm_openai_batch_items: int = Field(default=0, description="Строк отправлено в последний batched OpenAI‑запрос")
    llm_openai_http_ok: Optional[bool] = Field(default=None, description="None если OpenAI не вызывали")
    llm_truncated: bool = Field(default=False, description="True если кандидатов было больше max за один batch")
    llm_still_missing_ru: int = Field(default=0, description="После всех шагов: KO/ZH строк с пустым RU")


def _catalog_enrich_etag_if_stable(
    items: List[CatalogEnrichItem],
    *,
    settings: Settings,
    use_pg_in_request: bool,
    use_llm_in_request: bool,
) -> Optional[str]:
    """Weak ETag для детерминированной ветки (без LLM). Если LLM вкл — None."""
    if use_llm_in_request:
        return None
    rev = (settings.catalog_enrich_etag_revision or "").strip()
    canon = sorted(((it.domain.strip(), it.text.strip()) for it in items), key=lambda x: (x[0], x[1]))
    bundle = json.dumps(
        {
            "rev": rev,
            "api": settings.api_contract_version.strip(),
            "pg": bool(use_pg_in_request and settings.catalog_enrich_pg_cache_enabled),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ) + json.dumps(canon, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(bundle.encode("utf-8")).hexdigest()[:30]
    return f'W/"ce-{digest}"'


ALLOWED_PREVIEW = sorted(known_catalog_enrich_domains())


async def execute_catalog_enrichment(
    *,
    request: Request,
    items: List[CatalogEnrichItem],
    settings: Settings,
    use_pg_term_cache: bool,
    use_llm_fallback: bool,
    catalog_header_for_rate_limit: str | None,
    apply_rate_limit: bool,
) -> Tuple[CatalogEnrichResponse, Optional[str]]:
    """
    Общий пайплайн (публичный и internal роутеры). Выбрасывает HTTPException как раньше.
    """
    total_chars = sum(len((x.text or "")) for x in items)
    if total_chars > settings.catalog_enrich_max_payload_chars:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "catalog_enrich_payload_too_large",
                "chars": total_chars,
                "max": settings.catalog_enrich_max_payload_chars,
            },
        )

    allowed = known_catalog_enrich_domains()
    for it in items:
        dom = (it.domain or "").strip()
        if dom not in allowed:
            raise HTTPException(
                status_code=422,
                detail={"error": "unknown domain", "domain": dom, "allowed_sample": ALLOWED_PREVIEW[:24]},
            )

    redis = getattr(request.app.state, "redis", None)
    if apply_rate_limit:
        rl = getattr(request.client, "host", None) or ""
        rl_id = enrich_rate_identity(
            client_host=rl,
            enrich_header=catalog_header_for_rate_limit,
            enrich_secret_present=bool((settings.catalog_enrich_secret or "").strip()),
        )
        await enforce_catalog_enrich_rate_limit(
            redis=redis,
            key_prefix=(settings.redis_cache_prefix or "").strip(),
            bucket_id=rl_id,
            limit_per_minute=settings.catalog_enrich_rate_limit_per_minute,
        )

    rows = enrich_batch([(x.text.strip(), x.domain.strip()) for x in items])

    pg_hr = pg_he = pg_q = pg_rounds = 0
    pg_trunc = False

    if use_pg_term_cache:
        if not settings.catalog_enrich_pg_cache_enabled:
            raise HTTPException(
                status_code=400,
                detail="PG term cache is disabled on the server (set WRA_CATALOG_ENRICH_PG_CACHE_ENABLED=1)",
            )
        pool = getattr(request.app.state, "pg_pool", None)
        if pool is None:
            raise HTTPException(status_code=503, detail="PostgreSQL pool not available")
        pog = await enrich_rows_pg_term_cache(
            pool,
            rows,
            timeout_sec=float(settings.catalog_enrich_pg_timeout_sec),
            max_keys=int(settings.catalog_enrich_pg_max_keys),
            max_rounds=int(settings.catalog_enrich_pg_max_rounds),
        )
        pg_hr, pg_he, pg_q = pog.hits_ru, pog.hits_en, pog.keys_queried
        pg_trunc = pog.truncated
        pg_rounds = pog.rounds_executed

    llm_fallback_used = False
    llm_candidates = 0
    llm_memory_cache_hits = 0
    llm_redis_cache_hits = 0
    llm_openai_batch_items = 0
    llm_openai_http_ok: Optional[bool] = None
    llm_truncated = False
    llm_still_missing_ru = 0

    if use_llm_fallback:
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
        oc = await openai_enrich_missing(
            rows,
            settings=settings,
            max_llm_items=settings.catalog_enrich_llm_max_items,
            redis=redis,
        )
        llm_fallback_used = oc.fallback_used
        llm_candidates = oc.candidates
        llm_memory_cache_hits = oc.memory_cache_hits
        llm_redis_cache_hits = oc.redis_cache_hits
        llm_openai_batch_items = oc.openai_batches_items
        llm_openai_http_ok = oc.openai_ok
        llm_truncated = oc.truncated
        llm_still_missing_ru = oc.still_missing

    resp = CatalogEnrichResponse(
        result=[CatalogEnrichRow(**r) for r in rows],
        pg_cache_hits_ru=pg_hr,
        pg_cache_hits_en=pg_he,
        pg_cache_keys_queried=pg_q,
        pg_truncated=pg_trunc,
        pg_cache_rounds=pg_rounds,
        llm_fallback_used=llm_fallback_used,
        llm_candidates=llm_candidates,
        llm_memory_cache_hits=llm_memory_cache_hits,
        llm_redis_cache_hits=llm_redis_cache_hits,
        llm_openai_batch_items=llm_openai_batch_items,
        llm_openai_http_ok=llm_openai_http_ok,
        llm_truncated=llm_truncated,
        llm_still_missing_ru=llm_still_missing_ru,
    )
    etag = _catalog_enrich_etag_if_stable(
        items,
        settings=settings,
        use_pg_in_request=use_pg_term_cache,
        use_llm_in_request=use_llm_fallback,
    )
    return resp, etag


def _check_access(header_key: str | None) -> None:
    settings = get_settings()
    if not settings.catalog_enrich_enabled:
        raise HTTPException(status_code=404, detail="catalog enrich disabled")
    secret = (settings.catalog_enrich_secret or "").strip()
    if not secret:
        return
    if (header_key or "").strip() != secret:
        raise HTTPException(status_code=403, detail="invalid enrich key")


@router.post("/catalog/enrich-terms", response_model=CatalogEnrichResponse)
async def catalog_enrich_terms(
    request: Request,
    payload: CatalogEnrichRequest,
    response: Response,
    x_wra_catalog_enrich_key: str | None = Header(None, alias="X-WRA-Catalog-Enrich-Key"),
) -> CatalogEnrichResponse:
    """
    Статика → (опц.) Postgres term_translation_cache (read-only) → (опц.) LLM.
    Если тело без LLM и тот же ETag уже есть у клиента, можно реализовать If-None-Match на следующей версии роутера.
    """
    settings = get_settings()
    _check_access(x_wra_catalog_enrich_key)
    resp, etag = await execute_catalog_enrichment(
        request=request,
        items=list(payload.items),
        settings=settings,
        use_pg_term_cache=payload.use_pg_term_cache,
        use_llm_fallback=payload.use_llm_fallback,
        catalog_header_for_rate_limit=x_wra_catalog_enrich_key,
        apply_rate_limit=True,
    )
    if etag:
        response.headers["ETag"] = etag
    return resp
