from __future__ import annotations

import logging

from fastapi import APIRouter, status

from fastapi_app.schemas.api import WebVitalEvent

router = APIRouter(tags=["metrics"])
_log = logging.getLogger(__name__)


@router.post("/web-vitals", status_code=status.HTTP_202_ACCEPTED)
async def ingest_web_vitals(payload: WebVitalEvent) -> dict:
    """Lightweight ingestion endpoint for Next.js web-vitals beacon."""
    _log.info(
        "web-vitals name=%s value=%.3f rating=%s path=%s nav=%s",
        payload.name,
        payload.value,
        payload.rating or "-",
        payload.pathname or "-",
        payload.navigation_type or "-",
    )
    return {"ok": True}
