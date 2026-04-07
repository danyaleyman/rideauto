"""
Единая точка входа для кэшируемых JSON GET (ключ + TTL + compute).

Полноценный декоратор FastAPI не используется: у роутов разная сборка `flat`
(например `/car/{id}` добавляет `__car_ref__`).
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Tuple, Union

from fastapi import Request

from fastapi_app.cache import cache_key, cached_json_response

FlatInput = Union[Dict[str, str], Tuple[Tuple[str, str], ...]]


async def serve_cached_json(
    request: Request,
    *,
    segment: str,
    ttl_sec: int,
    flat: FlatInput,
    compute: Callable[[], Awaitable[Dict[str, Any]]],
) -> Dict[str, Any]:
    cache = request.app.state.cache
    prefix = getattr(request.app.state, "cache_key_prefix", "wra:api:cache")
    pairs = tuple(sorted(flat.items())) if isinstance(flat, dict) else flat
    key = cache_key(segment, pairs, prefix=prefix)
    return await cached_json_response(cache, key, ttl_sec, compute, segment=segment)
