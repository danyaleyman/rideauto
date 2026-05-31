"""B2C: сохранённые поиски каталога + уведомления на email."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from fastapi_app.config import Settings, get_settings
from fastapi_app.routers.auth import _require_user
from fastapi_app.schemas.api import AuthSimpleOkResponse
from fastapi_app.subscription_notify import run_all_subscription_notifications

router = APIRouter(tags=["subscriptions"])

_MAX_NAME = 120


class SubscriptionCreatePayload(BaseModel):
    name: str = Field(default="", max_length=_MAX_NAME)
    filters: Dict[str, Any] = Field(default_factory=dict)
    query_string: str = Field(default="", max_length=2000)
    market: str = Field(default="korea")
    notify_enabled: bool = True


class SubscriptionPatchPayload(BaseModel):
    name: Optional[str] = Field(default=None, max_length=_MAX_NAME)
    notify_enabled: Optional[bool] = None


def _admin_key_header(x_admin_key: Optional[str], settings: Settings) -> None:
    expected = (settings.subscriptions_admin_key or settings.cache_invalidate_secret or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="subscriptions_admin_disabled")
    if (x_admin_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _normalize_market(raw: str) -> str:
    m = (raw or "korea").strip().lower()
    if m == "china":
        return "china"
    return "korea"


def _row_to_item(row: asyncpg.Record) -> Dict[str, Any]:
    return {
        "id": str(row["public_id"]),
        "name": str(row["name"] or ""),
        "filters": row["filters"] if isinstance(row["filters"], dict) else json.loads(row["filters"] or "{}"),
        "query_string": str(row["query_string"] or ""),
        "market": str(row["market"] or "korea"),
        "notify_enabled": bool(row["notify_enabled"]),
        "last_notified_at": row["last_notified_at"].isoformat() if row["last_notified_at"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/subscriptions")
async def list_subscriptions(request: Request) -> Dict[str, Any]:
    settings = get_settings()
    user = await _require_user(request, settings)
    pool: asyncpg.Pool = request.app.state.pg_pool
    rows = await pool.fetch(
        """
        SELECT public_id, name, filters, query_string, market, notify_enabled,
               last_notified_at, created_at
        FROM search_subscriptions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user.id,
        int(settings.subscriptions_max_per_user),
    )
    return {"result": [_row_to_item(r) for r in rows]}


@router.post("/subscriptions", response_model=AuthSimpleOkResponse)
async def create_subscription(request: Request, payload: SubscriptionCreatePayload) -> AuthSimpleOkResponse:
    settings = get_settings()
    user = await _require_user(request, settings)
    market = _normalize_market(payload.market)
    name = (payload.name or "").strip()[:_MAX_NAME] or "Мой поиск"
    qs = (payload.query_string or "").strip()[:2000]
    filters = payload.filters or {}
    pool: asyncpg.Pool = request.app.state.pg_pool
    count = await pool.fetchval(
        "SELECT COUNT(*)::int FROM search_subscriptions WHERE user_id = $1",
        user.id,
    )
    if int(count or 0) >= int(settings.subscriptions_max_per_user):
        raise HTTPException(status_code=400, detail="subscription_limit")
    # dedupe same query_string
    existing = await pool.fetchval(
        """
        SELECT public_id FROM search_subscriptions
        WHERE user_id = $1 AND query_string = $2
        LIMIT 1
        """,
        user.id,
        qs,
    )
    if existing:
        await pool.execute(
            """
            UPDATE search_subscriptions
            SET name = $1, filters = $2::jsonb, market = $3, notify_enabled = $4, updated_at = now()
            WHERE user_id = $5 AND query_string = $6
            """,
            name,
            json.dumps(filters, ensure_ascii=False),
            market,
            bool(payload.notify_enabled),
            user.id,
            qs,
        )
        return AuthSimpleOkResponse(ok=True)
    await pool.execute(
        """
        INSERT INTO search_subscriptions (user_id, name, filters, query_string, market, notify_enabled)
        VALUES ($1, $2, $3::jsonb, $4, $5, $6)
        """,
        user.id,
        name,
        json.dumps(filters, ensure_ascii=False),
        qs,
        market,
        bool(payload.notify_enabled),
    )
    return AuthSimpleOkResponse(ok=True)


@router.patch("/subscriptions/{sid}", response_model=AuthSimpleOkResponse)
async def patch_subscription(
    request: Request,
    sid: str,
    payload: SubscriptionPatchPayload,
) -> AuthSimpleOkResponse:
    settings = get_settings()
    user = await _require_user(request, settings)
    try:
        UUID(sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid id") from exc
    if payload.name is None and payload.notify_enabled is None:
        raise HTTPException(status_code=400, detail="nothing_to_update")
    pool: asyncpg.Pool = request.app.state.pg_pool
    name = (payload.name or "").strip()[:_MAX_NAME] if payload.name is not None else None
    if name is not None and not name:
        name = "Мой поиск"
    if name is not None and payload.notify_enabled is not None:
        await pool.execute(
            """
            UPDATE search_subscriptions
            SET name = $1, notify_enabled = $2, updated_at = now()
            WHERE user_id = $3 AND public_id = $4::uuid
            """,
            name,
            bool(payload.notify_enabled),
            user.id,
            sid,
        )
    elif name is not None:
        await pool.execute(
            """
            UPDATE search_subscriptions
            SET name = $1, updated_at = now()
            WHERE user_id = $2 AND public_id = $3::uuid
            """,
            name,
            user.id,
            sid,
        )
    else:
        await pool.execute(
            """
            UPDATE search_subscriptions
            SET notify_enabled = $1, updated_at = now()
            WHERE user_id = $2 AND public_id = $3::uuid
            """,
            bool(payload.notify_enabled),
            user.id,
            sid,
        )
    return AuthSimpleOkResponse(ok=True)


@router.delete("/subscriptions/{sid}", response_model=AuthSimpleOkResponse)
async def delete_subscription(request: Request, sid: str) -> AuthSimpleOkResponse:
    settings = get_settings()
    user = await _require_user(request, settings)
    try:
        UUID(sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid id") from exc
    pool: asyncpg.Pool = request.app.state.pg_pool
    await pool.execute(
        "DELETE FROM search_subscriptions WHERE user_id = $1 AND public_id = $2::uuid",
        user.id,
        sid,
    )
    return AuthSimpleOkResponse(ok=True)


@router.post("/subscriptions/run-notifications")
async def run_notifications(
    request: Request,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> Dict[str, Any]:
    settings = get_settings()
    _admin_key_header(x_admin_key, settings)
    pool: asyncpg.Pool = request.app.state.pg_pool
    meili = request.app.state.meili
    return await run_all_subscription_notifications(pool, meili, settings)
