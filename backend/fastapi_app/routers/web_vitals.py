from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import asyncpg
from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from fastapi_app.config import get_settings
from fastapi_app.schemas.api import WebClientEvent, WebVitalEvent

router = APIRouter(tags=["metrics"])
_log = logging.getLogger(__name__)
_init_lock = asyncio.Lock()
_table_ready = False

_DDL = """
CREATE TABLE IF NOT EXISTS web_vitals_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL,
    name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    rating TEXT,
    delta DOUBLE PRECISION,
    navigation_type TEXT,
    pathname TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_web_vitals_created_at ON web_vitals_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_web_vitals_name_created ON web_vitals_events (name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_web_vitals_path_created ON web_vitals_events (pathname, created_at DESC);

CREATE TABLE IF NOT EXISTS web_client_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    pathname TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_web_client_events_created ON web_client_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_web_client_events_type_created ON web_client_events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_web_client_events_session_created ON web_client_events (session_id, created_at DESC);
"""


async def _ensure_table(pool: asyncpg.Pool) -> None:
    global _table_ready
    if _table_ready:
        return
    async with _init_lock:
        if _table_ready:
            return
        async with pool.acquire() as conn:
            await conn.execute(_DDL)
        _table_ready = True


@router.post("/web-vitals", status_code=status.HTTP_202_ACCEPTED)
async def ingest_web_vitals(request: Request, payload: WebVitalEvent) -> dict:
    """Ingest Next.js web-vitals events and persist to PostgreSQL."""
    pool: asyncpg.Pool = request.app.state.pg_pool
    await _ensure_table(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO web_vitals_events
                (event_id, name, value, rating, delta, navigation_type, pathname, user_agent)
            VALUES
                ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            payload.id,
            payload.name,
            float(payload.value),
            payload.rating,
            float(payload.delta) if payload.delta is not None else None,
            payload.navigation_type,
            payload.pathname,
            payload.user_agent,
        )
    _log.info(
        "web-vitals name=%s value=%.3f rating=%s path=%s nav=%s",
        payload.name,
        payload.value,
        payload.rating or "-",
        payload.pathname or "-",
        payload.navigation_type or "-",
    )
    return {"ok": True}


@router.post("/web-events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_web_events(request: Request, payload: WebClientEvent) -> dict:
    """Ingest client-side behavioral logs (filter interactions/errors)."""
    pool: asyncpg.Pool = request.app.state.pg_pool
    await _ensure_table(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO web_client_events
                (session_id, event_type, payload, pathname, user_agent)
            VALUES
                ($1, $2, $3::jsonb, $4, $5)
            """,
            payload.session_id[:128],
            payload.event_type[:64],
            payload.payload,
            payload.pathname,
            payload.user_agent,
        )
    _log.info(
        "web-event type=%s session=%s path=%s payload=%s",
        payload.event_type,
        payload.session_id[:12],
        payload.pathname or "-",
        str(payload.payload)[:400],
    )
    return {"ok": True}


@router.get("/ops/web-vitals-summary")
async def web_vitals_summary(
    request: Request,
    minutes: int = Query(default=60, ge=1, le=10080),
    path: Optional[str] = Query(default=None),
    x_wra_admin_key: Optional[str] = Header(default=None, alias="X-WRA-Admin-Key"),
) -> Dict[str, Any]:
    """Simple aggregated dashboard endpoint for recent web-vitals data."""
    secret = (get_settings().cache_invalidate_secret or "").strip()
    if secret and (x_wra_admin_key or "").strip() != secret:
        raise HTTPException(status_code=401, detail="unauthorized")

    pool: asyncpg.Pool = request.app.state.pg_pool
    await _ensure_table(pool)

    where = "created_at >= now() - ($1::text || ' minutes')::interval"
    params: list[Any] = [minutes]
    if path and path.strip():
        where += " AND pathname = $2"
        params.append(path.strip())

    sql = f"""
        SELECT
            name,
            count(*)::int AS samples,
            round(avg(value)::numeric, 2)::float8 AS avg,
            round(percentile_cont(0.50) WITHIN GROUP (ORDER BY value)::numeric, 2)::float8 AS p50,
            round(percentile_cont(0.75) WITHIN GROUP (ORDER BY value)::numeric, 2)::float8 AS p75,
            round(percentile_cont(0.95) WITHIN GROUP (ORDER BY value)::numeric, 2)::float8 AS p95
        FROM web_vitals_events
        WHERE {where}
        GROUP BY name
        ORDER BY name
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
        total_samples = await conn.fetchval(
            f"SELECT count(*)::int FROM web_vitals_events WHERE {where}",
            *params,
        )

    items = [dict(r) for r in rows]
    return {
        "ok": True,
        "window_minutes": minutes,
        "path": path or None,
        "samples_total": int(total_samples or 0),
        "metrics": items,
    }
