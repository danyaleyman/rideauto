"""Ограничение частоты POST /catalog/enrich-terms (Redis счётчик по минуте или память процесса)."""
from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any, Optional

from fastapi import HTTPException


_RL_LOCK = asyncio.Lock()
_RL_ANON: dict[str, tuple[int, int]] = {}


def _minute_bucket() -> int:
    return int(time.time() // 60)


def enrich_rate_identity(*, client_host: str, enrich_header: str | None, enrich_secret_present: bool) -> str:
    host = (client_host or "unknown").strip() or "unknown"
    if enrich_secret_present and (enrich_header or "").strip():
        hdr = (enrich_header or "").strip()
        return hashlib.sha256(f"h:{hdr}".encode("utf-8")).hexdigest()[:24]
    return hashlib.sha256(f"i:{host}".encode("utf-8")).hexdigest()[:24]


async def enforce_catalog_enrich_rate_limit(
    *,
    redis: Optional[Any],
    key_prefix: str,
    bucket_id: str,
    limit_per_minute: int,
) -> None:
    """limit_per_minute=0 — без лимита."""
    if limit_per_minute <= 0:
        return
    pref = (key_prefix or "wra:api:cache").strip().rstrip(":")
    mb = _minute_bucket()
    redis_err = False

    if redis is not None:
        k = f"{pref}:rl:cat_enrich:v1:{bucket_id}:{mb}"
        try:
            n_raw = await redis.incr(k)
            n_int = int(n_raw) if isinstance(n_raw, int) else int(str(n_raw))
            if n_int == 1:
                await redis.expire(k, 90)
            if n_int > limit_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "catalog_enrich_rate_limit",
                        "hint": "lower batch frequency or chunk items server-side",
                    },
                )
            return
        except HTTPException:
            raise
        except Exception:
            redis_err = True

    if redis is None or redis_err:
        await _enforce_memory_fallback(bucket_id, mb, limit_per_minute)


async def _enforce_memory_fallback(bucket_id: str, mb: int, limit: int) -> None:
    async with _RL_LOCK:
        prev = _RL_ANON.get(bucket_id)
        if prev is None or prev[0] != mb:
            _RL_ANON[bucket_id] = (mb, 1)
            return
        n = prev[1] + 1
        _RL_ANON[bucket_id] = (mb, n)
        if n > limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "catalog_enrich_rate_limit",
                    "hint": "lower batch frequency; multi-worker setups should use WRA_REDIS_URL",
                },
            )
