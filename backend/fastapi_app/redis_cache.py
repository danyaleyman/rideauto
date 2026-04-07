"""
Асинхронный Redis-слой для JSON-ответов каталога.

Ключи: `{prefix}:{segment}:{sha256(sorted query items)}`
Инвалидация: `purge_segment("search" | "facets" | "car")` или `purge_all()`.

Стратегия инвалидации (в дополнение к TTL):
- `POST /api/internal/cache/invalidate` — по секрету (WRA_CACHE_INVALIDATE_SECRET), scope=all|search|facets|car.
- После полного reindex / массового импорта — `scope=all`.
- После правки одной карточки достаточно `search` + `facets` (+ `car`, если кэшируете карточку по id).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

import redis.asyncio as aioredis

from fastapi_app.cache import cache_key

_log = logging.getLogger(__name__)


class RedisJSONCache:
    def __init__(self, client: aioredis.Redis, *, key_prefix: str = "wra:api:cache") -> None:
        self._r = client
        self._prefix = key_prefix.strip().rstrip(":")

    def make_key(self, segment: str, flat: Tuple[Tuple[str, str], ...]) -> str:
        return cache_key(segment, flat, prefix=self._prefix)

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        raw = await self._r.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            _log.warning("redis cache JSON decode failed for key %s; treating as miss", key[:80])
            try:
                await self._r.unlink(key)
            except Exception:
                pass
            return None
        if not isinstance(val, dict):
            _log.warning("redis cache had non-object JSON for key %s; dropping", key[:80])
            try:
                await self._r.unlink(key)
            except Exception:
                pass
            return None
        return val

    async def set_json(self, key: str, value: Dict[str, Any], ttl_sec: int) -> None:
        if ttl_sec <= 0:
            return
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        await self._r.setex(key, ttl_sec, payload)

    async def purge_segment(self, segment: str) -> int:
        pattern = f"{self._prefix}:{segment}:*"
        return await self._unlink_pattern(pattern)

    async def purge_all(self) -> int:
        pattern = f"{self._prefix}:*"
        return await self._unlink_pattern(pattern)

    async def _unlink_pattern(self, pattern: str) -> int:
        n = 0
        async for k in self._r.scan_iter(match=pattern, count=256):
            await self._r.unlink(k)
            n += 1
        return n


def create_redis_client(url: str) -> aioredis.Redis:
    return aioredis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis_client(client: Optional[aioredis.Redis]) -> None:
    if client is not None:
        await client.aclose()
