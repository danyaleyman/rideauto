"""Web Push subscribe (B2C, authenticated)."""
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from fastapi_app.config import get_settings
from fastapi_app.routers.auth import _require_user
from fastapi_app.schemas.api import AuthSimpleOkResponse

router = APIRouter(tags=["push"])


class PushKeysPayload(BaseModel):
    p256dh: str = Field(..., min_length=10, max_length=500)
    auth: str = Field(..., min_length=10, max_length=500)


class PushSubscribePayload(BaseModel):
    endpoint: str = Field(..., min_length=20, max_length=2000)
    keys: PushKeysPayload


@router.get("/push/vapid-public-key")
async def vapid_public_key() -> Dict[str, str]:
    settings = get_settings()
    pub = (settings.push_vapid_public_key or "").strip()
    if not pub:
        raise HTTPException(status_code=503, detail="push_not_configured")
    return {"public_key": pub}


@router.post("/push/subscribe", response_model=AuthSimpleOkResponse)
async def push_subscribe(request: Request, payload: PushSubscribePayload) -> AuthSimpleOkResponse:
    settings = get_settings()
    if not (settings.push_vapid_public_key or "").strip():
        raise HTTPException(status_code=503, detail="push_not_configured")
    user = await _require_user(request, settings)
    pool = request.app.state.pg_pool
    ua = (request.headers.get("user-agent") or "")[:500]
    await pool.execute(
        """
        INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, endpoint) DO UPDATE
        SET p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth, user_agent = EXCLUDED.user_agent
        """,
        user.id,
        payload.endpoint.strip(),
        payload.keys.p256dh.strip(),
        payload.keys.auth.strip(),
        ua or None,
    )
    return AuthSimpleOkResponse(ok=True)


@router.delete("/push/subscribe", response_model=AuthSimpleOkResponse)
async def push_unsubscribe(
    request: Request,
    endpoint: str = Query(..., min_length=20),
) -> AuthSimpleOkResponse:
    settings = get_settings()
    user = await _require_user(request, settings)
    pool = request.app.state.pg_pool
    await pool.execute(
        "DELETE FROM push_subscriptions WHERE user_id = $1 AND endpoint = $2",
        user.id,
        endpoint.strip(),
    )
    return AuthSimpleOkResponse(ok=True)
