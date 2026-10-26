"""Ручная публикация лота в канал и автопостинг 3–4 выгодных предложений в день."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from fastapi_app.config import Settings, get_settings
from fastapi_app.image_service import (
    ImageServiceError,
    ensure_cached_webp,
    parse_allowed_hosts,
)
from fastapi_app.meilisearch_query import build_meilisearch_filter, meilisearch_sort_list
from fastapi_app.pg_catalog import fetch_car_any_id, fetch_cars_by_ids
from fastapi_app.rf_popular_models import is_rf_popular_listing
from fastapi_app.routers.auth import AuthUserResponse, require_listing_admin
from read_models import build_catalog_read_model
from fastapi_app.telegram_channel import (
    build_car_title,
    build_channel_caption,
    build_channel_html,
    caption_to_html,
    channel_public_origin,
    channel_telegram_configured,
    collect_photo_urls,
    has_turnkey_customs_price,
    is_petrol_or_diesel,
    public_proxy_photo_urls,
    score_channel_deal,
    send_channel_article_sync,
    source_to_market,
)

router = APIRouter(tags=["telegram-channel"])
_log = logging.getLogger(__name__)
_init_lock = asyncio.Lock()
_table_ready = False

_DDL = """
CREATE TABLE IF NOT EXISTS telegram_channel_posts (
    car_id TEXT PRIMARY KEY,
    source TEXT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    telegram_message_id BIGINT,
    telegram_chat_id TEXT,
    origin TEXT NOT NULL,
    posted_by TEXT,
    title TEXT,
    mode TEXT
);
CREATE INDEX IF NOT EXISTS idx_telegram_channel_posts_posted_at
    ON telegram_channel_posts (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_telegram_channel_posts_origin_day
    ON telegram_channel_posts (origin, posted_at DESC);
"""


class PublishTelegramPayload(BaseModel):
    text: Optional[str] = Field(default=None, max_length=32_000)
    photo_urls: Optional[List[str]] = Field(default=None, max_length=10)
    force: bool = False


class AutopostPayload(BaseModel):
    limit: int = Field(default=1, ge=1, le=8)
    ignore_daily_limit: bool = False


async def _ensure_table(pool: asyncpg.Pool) -> None:
    global _table_ready
    if _table_ready:
        return
    async with _init_lock:
        if _table_ready:
            return
        await pool.execute(_DDL)
        _table_ready = True


def _admin_key_header(x_admin_key: Optional[str], settings: Settings) -> None:
    expected = (settings.subscriptions_admin_key or settings.cache_invalidate_secret or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="telegram_autopost_disabled")
    if (x_admin_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _as_mapping(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row)


def _flatten_catalog_data(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    inner = raw.get("data")
    if isinstance(inner, dict):
        merged = dict(inner)
        for k, v in raw.items():
            if k != "data" and k not in merged:
                merged[k] = v
        return merged
    return dict(raw)


def _car_bundle(row: Any) -> tuple[str, Dict[str, Any]]:
    """car_id + плоский data и для fetch_car_any_id (dict), и для SELECT кандидатов."""
    mapping = _as_mapping(row)
    nested = mapping.get("data")
    data = _flatten_catalog_data(nested) if isinstance(nested, dict) else _flatten_catalog_data(mapping)
    for col in (
        "source",
        "mark",
        "model",
        "generation",
        "trim_name",
        "price_rub",
        "mileage_km",
        "year",
        "year_month",
        "power_hp",
        "power_kw",
        "torque_nm",
        "displacement_cc",
        "displacement_label",
        "fuel_type",
        "transmission_type",
        "drive_type",
        "km_age",
    ):
        if mapping.get(col) is not None and data.get(col) in (None, ""):
            data[col] = mapping[col]
    car_id = str(mapping.get("car_id") or mapping.get("id") or data.get("id") or "").strip()
    return car_id, data


def _row_price(mapping: Dict[str, Any], data: Dict[str, Any]) -> Optional[float]:
    for cand in (
        mapping.get("price_rub"),
        data.get("price_rub"),
        data.get("my_price"),
        data.get("final_price_rub"),
    ):
        try:
            if cand is None or cand == "":
                continue
            n = float(cand)
            if n > 0:
                return n
        except (TypeError, ValueError):
            continue
    return None


async def _already_posted(pool: asyncpg.Pool, car_id: str) -> Optional[asyncpg.Record]:
    return await pool.fetchrow(
        "SELECT car_id, posted_at, telegram_message_id, origin FROM telegram_channel_posts WHERE car_id = $1",
        car_id,
    )


async def _today_autopost_counts(pool: asyncpg.Pool) -> Dict[str, int]:
    rows = await pool.fetch(
        """
        SELECT source, COUNT(*)::int AS n
        FROM telegram_channel_posts
        WHERE origin = 'autopost'
          AND posted_at >= date_trunc('day', timezone('Asia/Yekaterinburg', now()))
                           AT TIME ZONE 'Asia/Yekaterinburg'
        GROUP BY source
        """
    )
    korea = 0
    china = 0
    for row in rows:
        market = source_to_market(row["source"])
        if market == "korea":
            korea += int(row["n"] or 0)
        elif market == "china":
            china += int(row["n"] or 0)
    return {"korea": korea, "china": china, "total": korea + china}


async def _today_autopost_count(pool: asyncpg.Pool) -> int:
    return (await _today_autopost_counts(pool))["total"]


def _next_autopost_market(
    counts: Dict[str, int],
    settings: Settings,
    *,
    ignore_daily_limit: bool = False,
) -> Optional[str]:
    if ignore_daily_limit:
        if int(counts.get("korea") or 0) <= int(counts.get("china") or 0):
            return "korea"
        return "china"
    korea_left = int(settings.channel_telegram_korea_daily_limit) - int(counts.get("korea") or 0)
    china_left = int(settings.channel_telegram_china_daily_limit) - int(counts.get("china") or 0)
    if korea_left <= 0 and china_left <= 0:
        return None
    if korea_left <= 0:
        return "china"
    if china_left <= 0:
        return "korea"
    if int(counts.get("korea") or 0) <= int(counts.get("china") or 0):
        return "korea"
    return "china"


async def _warm_public_photos(
    originals: List[str],
    settings: Settings,
    redis: Any,
) -> List[str]:
    origin = channel_public_origin(settings)
    proxies = public_proxy_photo_urls(origin, originals)
    allowed = parse_allowed_hosts(settings.image_allowed_hosts)
    cache_dir = Path(settings.image_cache_dir)

    async def _warm(src: str, public: str) -> None:
        try:
            digest = public.rsplit("/images/", 1)[-1].split("?", 1)[0]
            await ensure_cached_webp(
                digest=digest,
                size="medium",
                src=src,
                cache_dir=cache_dir,
                allowed_hosts=allowed,
                fetch_timeout=min(20.0, float(settings.image_fetch_timeout_sec)),
                max_bytes=settings.image_max_fetch_bytes,
                redis=redis,
                redis_ttl_sec=settings.image_src_redis_ttl_sec,
                referer_for_encar=(settings.image_encar_referer or "").strip() or None,
                referer_for_che168=(settings.image_che168_referer or "").strip() or None,
                referer_for_autotrader=(settings.image_autotrader_referer or "").strip() or None,
            )
        except ImageServiceError as exc:
            _log.info("telegram photo warm skipped %s: %s", src[:80], exc)
        except Exception as exc:  # noqa: BLE001
            _log.info("telegram photo warm failed %s: %s", src[:80], exc)

    await asyncio.gather(*[_warm(src, public) for src, public in zip(originals, proxies)])
    return proxies


async def _publish_row(
    *,
    pool: asyncpg.Pool,
    row: asyncpg.Record,
    settings: Settings,
    redis: Any,
    origin: str,
    posted_by: Optional[str],
    text_override: Optional[str],
    photo_override: Optional[List[str]],
    force: bool,
) -> Dict[str, Any]:
    mapping = _as_mapping(row)
    car_id, data = _car_bundle(row)
    if not car_id:
        raise HTTPException(status_code=404, detail="not found")
    existing = await _already_posted(pool, car_id)
    if existing and not force:
        posted = existing["posted_at"]
        return {
            "ok": True,
            "already": True,
            "car_id": car_id,
            "posted_at": posted.isoformat() if posted else None,
            "message_id": existing["telegram_message_id"],
        }
    title = build_car_title(
        mark=data.get("mark"),
        model=data.get("model"),
        generation=data.get("generation"),
        fallback=car_id,
    )
    price = _row_price(mapping, data)
    market = source_to_market(mapping.get("source") or data.get("source") or data.get("market"))
    photos = [u.strip() for u in (photo_override or []) if isinstance(u, str) and u.strip()]
    if not photos:
        photos = collect_photo_urls(data)
    if not photos:
        raise HTTPException(status_code=400, detail="telegram_no_photos")
    caption_kwargs = dict(
        title=title,
        data=data,
        price_rub=price,
        market=market,
        published_at=datetime.now(),
        buy_url=settings.channel_telegram_buy_url,
        manager_url=settings.channel_telegram_manager_url,
    )
    caption = (text_override or "").strip() or build_channel_caption(**caption_kwargs)
    html_body = caption_to_html(caption) if (text_override or "").strip() else build_channel_html(**caption_kwargs)
    public_urls = await _warm_public_photos(photos[:10], settings, redis)
    try:
        sent = await asyncio.to_thread(
            send_channel_article_sync,
            photo_urls=public_urls,
            text=caption,
            html_body=html_body,
            settings=settings,
        )
    except RuntimeError as exc:
        _log.exception("telegram channel publish failed for %s", car_id)
        raise HTTPException(status_code=502, detail=str(exc)[:400]) from exc
    await pool.execute(
        """
        INSERT INTO telegram_channel_posts
            (car_id, source, posted_at, telegram_message_id, telegram_chat_id, origin, posted_by, title, mode)
        VALUES ($1, $2, now(), $3, $4, $5, $6, $7, $8)
        ON CONFLICT (car_id) DO UPDATE SET
            posted_at = EXCLUDED.posted_at,
            telegram_message_id = EXCLUDED.telegram_message_id,
            telegram_chat_id = EXCLUDED.telegram_chat_id,
            origin = EXCLUDED.origin,
            posted_by = EXCLUDED.posted_by,
            title = EXCLUDED.title,
            mode = EXCLUDED.mode
        """,
        car_id,
        str(mapping.get("source") or data.get("source") or market),
        sent.get("message_id"),
        (settings.channel_telegram_chat_id or "").strip(),
        origin,
        posted_by,
        title,
        sent.get("mode"),
    )
    return {
        "ok": True,
        "already": False,
        "car_id": car_id,
        "title": title,
        "mode": sent.get("mode"),
        "message_id": sent.get("message_id"),
        "photos": len(public_urls),
    }


async def _pick_autopost_candidates(
    pool: asyncpg.Pool,
    settings: Settings,
    market: str,
    meili: Any = None,
) -> List[Any]:
    ids: List[str] = []
    if meili is not None:
        flat = {
            "region": market,
            "full_customs_only": "1",
            "price_from": "500000",
            "price_to": "6500000",
            "year_from": "2016",
        }
        filt = build_meilisearch_filter(flat)
        idx = meili.index(settings.meilisearch_index)
        opts: Dict[str, Any] = {
            "limit": 160,
            "sort": meilisearch_sort_list("date_new"),
            "attributesToRetrieve": ["id"],
        }
        if filt:
            opts["filter"] = filt

        def _run() -> Any:
            return idx.search("", opts)

        try:
            ms = await asyncio.to_thread(_run)
            ids = [str(h.get("id") or "").strip() for h in (ms.get("hits") or [])]
            ids = [x for x in ids if x]
        except Exception as exc:  # noqa: BLE001
            _log.warning("telegram autopost meili pick failed: %s", exc)
            ids = []
    if not ids:
        return []
    posted = await pool.fetch(
        "SELECT car_id FROM telegram_channel_posts WHERE car_id = ANY($1::text[])",
        ids,
    )
    posted_ids = {str(r["car_id"]) for r in posted}
    by_id = await fetch_cars_by_ids(pool, ids)
    out: List[Any] = []
    for cid in ids:
        if cid in posted_ids:
            continue
        car = by_id.get(cid)
        if car:
            out.append(car)
    return out


def _best_candidate(rows: List[Any], min_photos: int) -> Optional[Any]:
    ranked: List[tuple[float, Any]] = []
    for row in rows:
        _cid, data = _car_bundle(row)
        try:
            rm = build_catalog_read_model(data, use_clean=True)
        except Exception:  # noqa: BLE001
            rm = {}
        if isinstance(rm, dict):
            if rm.get("engine_type") and not data.get("engine_type"):
                data["engine_type"] = rm["engine_type"]
            if rm.get("pricing_tier"):
                data["pricing_tier"] = rm["pricing_tier"]
            if rm.get("customs_included") is not None:
                data["customs_included"] = rm["customs_included"]
            if rm.get("price_on_request") is not None:
                data["price_on_request"] = rm["price_on_request"]
        if not is_petrol_or_diesel(data):
            continue
        if not is_rf_popular_listing(data, _as_mapping(row)):
            continue
        price = _row_price(_as_mapping(row), data)
        if price is None and isinstance(rm, dict):
            try:
                price = float(rm["price_rub"]) if rm.get("price_rub") is not None else None
            except (TypeError, ValueError):
                price = None
        if not has_turnkey_customs_price(data, price):
            continue
        photos = collect_photo_urls(data)
        if len(photos) < min_photos:
            continue
        ranked.append(
            (
                score_channel_deal(
                    source=str(row.get("source") or ""),
                    price_rub=float(row["price_rub"]) if row.get("price_rub") is not None else None,
                    mileage_km=int(row["mileage_km"]) if row.get("mileage_km") is not None else None,
                    year=int(row["year"]) if row.get("year") is not None else None,
                    photo_count=len(photos),
                    damaged_parts=int(row["damaged_parts_count"])
                    if row.get("damaged_parts_count") is not None
                    else None,
                ),
                row,
            )
        )
    if not ranked:
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


@router.get("/telegram/channel/status")
async def telegram_channel_status(request: Request) -> Dict[str, Any]:
    await require_listing_admin(request)
    settings = get_settings()
    pool: asyncpg.Pool = request.app.state.pg_pool
    await _ensure_table(pool)
    today = await _today_autopost_counts(pool)
    return {
        "configured": channel_telegram_configured(settings),
        "chat_id": (settings.channel_telegram_chat_id or "").strip() or None,
        "daily_limit": int(settings.channel_telegram_korea_daily_limit)
        + int(settings.channel_telegram_china_daily_limit),
        "korea_daily_limit": int(settings.channel_telegram_korea_daily_limit),
        "china_daily_limit": int(settings.channel_telegram_china_daily_limit),
        "today_autoposts": today["total"],
        "today_korea": today["korea"],
        "today_china": today["china"],
    }


@router.get("/telegram/channel/cars/{car_ref}")
async def telegram_car_status(car_ref: str, request: Request) -> Dict[str, Any]:
    await require_listing_admin(request)
    pool: asyncpg.Pool = request.app.state.pg_pool
    await _ensure_table(pool)
    row = await fetch_car_any_id(pool, car_ref)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    car_id, _data = _car_bundle(row)
    posted = await _already_posted(pool, car_id)
    if not posted:
        return {"posted": False, "car_id": car_id}
    at = posted["posted_at"]
    return {
        "posted": True,
        "car_id": car_id,
        "posted_at": at.isoformat() if at else None,
        "message_id": posted["telegram_message_id"],
        "origin": posted["origin"],
    }


@router.post("/telegram/channel/cars/{car_ref}")
async def publish_car_to_channel(
    car_ref: str,
    request: Request,
    payload: PublishTelegramPayload,
) -> Dict[str, Any]:
    user: AuthUserResponse = await require_listing_admin(request)
    settings = get_settings()
    if not channel_telegram_configured(settings):
        raise HTTPException(status_code=503, detail="telegram_channel_not_configured")
    pool: asyncpg.Pool = request.app.state.pg_pool
    await _ensure_table(pool)
    row = await fetch_car_any_id(pool, car_ref)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return await _publish_row(
        pool=pool,
        row=row,
        settings=settings,
        redis=getattr(request.app.state, "redis", None),
        origin="manual",
        posted_by=(user.email or "").strip().lower() or None,
        text_override=payload.text,
        photo_override=payload.photo_urls,
        force=payload.force,
    )


@router.post("/telegram/channel/autopost")
async def run_channel_autopost(
    request: Request,
    payload: AutopostPayload | None = None,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> Dict[str, Any]:
    settings = get_settings()
    _admin_key_header(x_admin_key, settings)
    if not channel_telegram_configured(settings):
        raise HTTPException(status_code=503, detail="telegram_channel_not_configured")
    pool: asyncpg.Pool = request.app.state.pg_pool
    meili = getattr(request.app.state, "meili", None)
    await _ensure_table(pool)
    want = int((payload.limit if payload else 1) or 1)
    ignore_quota = bool(payload.ignore_daily_limit) if payload else False
    posted: List[Dict[str, Any]] = []
    skipped_today = 0
    for _ in range(want):
        today = await _today_autopost_counts(pool)
        market = _next_autopost_market(today, settings, ignore_daily_limit=ignore_quota)
        if not market:
            skipped_today = today["total"]
            break
        try:
            candidates = await _pick_autopost_candidates(pool, settings, market, meili)
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail="telegram_autopost_picker_timeout") from exc
        best = _best_candidate(candidates, int(settings.channel_telegram_min_photos))
        if not best:
            other = "china" if market == "korea" else "korea"
            other_left = (
                int(settings.channel_telegram_china_daily_limit) - int(today.get("china") or 0)
                if other == "china"
                else int(settings.channel_telegram_korea_daily_limit) - int(today.get("korea") or 0)
            )
            if ignore_quota or other_left > 0:
                try:
                    candidates = await _pick_autopost_candidates(pool, settings, other, meili)
                except TimeoutError as exc:
                    raise HTTPException(status_code=504, detail="telegram_autopost_picker_timeout") from exc
                best = _best_candidate(candidates, int(settings.channel_telegram_min_photos))
            if not best:
                break
        posted.append(
            await _publish_row(
                pool=pool,
                row=best,
                settings=settings,
                redis=getattr(request.app.state, "redis", None),
                origin="autopost",
                posted_by="cron",
                text_override=None,
                photo_override=None,
                force=False,
            )
        )
    today = await _today_autopost_counts(pool)
    return {
        "ok": True,
        "posted": posted,
        "today_autoposts": today["total"],
        "today_korea": today["korea"],
        "today_china": today["china"],
        "daily_limit": int(settings.channel_telegram_korea_daily_limit)
        + int(settings.channel_telegram_china_daily_limit),
        "skipped_daily_limit": skipped_today or None,
    }
