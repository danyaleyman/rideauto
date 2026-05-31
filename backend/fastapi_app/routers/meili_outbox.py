"""Admin: обработка PG→Meili outbox."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request

from fastapi_app.config import Settings, get_settings
from fastapi_app.meili_outbox import process_meili_outbox_batch

router = APIRouter(tags=["ops"])


def _admin_key_header(x_admin_key: Optional[str], settings: Settings) -> None:
    expected = (settings.subscriptions_admin_key or settings.cache_invalidate_secret or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="meili_outbox_admin_disabled")
    if (x_admin_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/meili/outbox/process")
async def process_outbox(
    request: Request,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    limit: int = Query(default=200, ge=1, le=2000),
) -> Dict[str, Any]:
    settings = get_settings()
    _admin_key_header(x_admin_key, settings)
    pool = request.app.state.pg_pool
    meili = request.app.state.meili
    return await process_meili_outbox_batch(pool, meili, settings, limit=limit)
