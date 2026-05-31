"""B2C: просмотр заявок с сайта (listing admin email + session)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query, Request

from fastapi_app.routers.auth import AuthUserResponse, require_listing_admin

router = APIRouter(tags=["forms"])


async def _listing_admin_guard(request: Request) -> AuthUserResponse:
    return await require_listing_admin(request)


@router.get("/leads/admin")
async def list_leads_admin(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Последние заявки — только для email из WRA_LISTING_ADMIN_EMAILS (magic-link сессия)."""
    await _listing_admin_guard(request)
    pool = request.app.state.pg_pool
    rows = await pool.fetch(
        """
        SELECT id, full_name, contact_method, message, pd_agree, ip, email_sent, created_at
        FROM lead_requests
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """,
        int(limit),
        int(offset),
    )
    total = await pool.fetchval("SELECT COUNT(*)::int FROM lead_requests")
    items = [
        {
            "id": int(r["id"]),
            "full_name": str(r["full_name"]),
            "contact_method": str(r["contact_method"]),
            "message": str(r["message"]),
            "pd_agree": bool(r["pd_agree"]),
            "ip": r["ip"],
            "email_sent": bool(r["email_sent"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"result": items, "total": int(total or 0), "limit": limit, "offset": offset}
