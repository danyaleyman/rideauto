from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request

from fastapi_app.config import get_settings

router = APIRouter(tags=["internal"])


class CacheScope(str, Enum):
    all = "all"
    search = "search"
    facets = "facets"
    car = "car"


@router.post("/internal/cache/invalidate")
async def invalidate_cache(
    request: Request,
    scope: CacheScope = Query(default=CacheScope.all, description="Область сброса ключей"),
    x_wra_admin_key: Optional[str] = Header(default=None, alias="X-WRA-Admin-Key"),
) -> Dict[str, Any]:
    """
    Сброс кэша по шаблону ключей (только при активном Redis).

    Заголовок `X-WRA-Admin-Key` должен совпадать с `WRA_CACHE_INVALIDATE_SECRET`.
    """
    settings = get_settings()
    secret = (settings.cache_invalidate_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="cache_invalidate_disabled",
        )
    if (x_wra_admin_key or "").strip() != secret:
        raise HTTPException(status_code=401, detail="unauthorized")

    cache = request.app.state.cache
    purged: Dict[str, int] = {}

    if scope == CacheScope.all:
        purged["_total"] = await cache.purge_all()
    else:
        seg = scope.value
        purged[seg] = await cache.purge_segment(seg)

    return {"ok": True, "scope": scope.value, "purged": purged}
