from __future__ import annotations



import hashlib

import json

from typing import Any, Awaitable, Callable, Dict, Optional, Protocol, Tuple, TypeVar

from fastapi_app.config import get_settings
from fastapi_app.metrics.prometheus import inc_cache_lookup


T = TypeVar("T")




def params_signature(flat: Tuple[Tuple[str, str], ...]) -> str:

    """Детерминированный SHA256 от отсортированных пар query (ключ кэша)."""

    body = json.dumps(flat, ensure_ascii=False, sort_keys=True).encode("utf-8")

    return hashlib.sha256(body).hexdigest()





def cache_key(

    segment: str,

    flat: Tuple[Tuple[str, str], ...],

    *,

    prefix: str = "wra:api:cache",

) -> str:

    """Полный ключ Redis: `{prefix}:{segment}:{sha256}`; для NoOpCache — только логический идентификатор."""

    p = prefix.strip().rstrip(":")

    return f"{p}:{segment}:{params_signature(flat)}"





def cache_key_for_query(prefix: str, flat: Tuple[Tuple[str, str], ...]) -> str:

    """Обратная совместимость: `prefix` = логическое имя сегмента (`search` / `facets` / `car`)."""

    return cache_key(prefix, flat, prefix="wra:api:cache")





class CacheBackend(Protocol):

    """Бэкенд ответов API; Redis-реализация — `RedisJSONCache`."""



    async def get_json(self, key: str) -> Optional[Dict[str, Any]]: ...



    async def set_json(self, key: str, value: Dict[str, Any], ttl_sec: int) -> None: ...



    async def purge_segment(self, segment: str) -> int: ...



    async def purge_all(self) -> int: ...





class NoOpCache:

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:

        return None



    async def set_json(self, key: str, value: Dict[str, Any], ttl_sec: int) -> None:

        return None



    async def purge_segment(self, segment: str) -> int:

        return 0



    async def purge_all(self) -> int:

        return 0





async def cached_json_response(
    cache: CacheBackend,
    key: str,
    ttl_sec: int,
    compute: Callable[[], Awaitable[Dict[str, Any]]],
    *,
    segment: str = "unknown",
) -> Dict[str, Any]:
    if ttl_sec <= 0:
        return await compute()

    hit = await cache.get_json(key)
    metrics_on = get_settings().metrics_enabled
    if hit is not None:
        if metrics_on:
            inc_cache_lookup(segment, hit=True)
        return hit
    if metrics_on:
        inc_cache_lookup(segment, hit=False)

    data = await compute()
    await cache.set_json(key, data, ttl_sec)
    return data
