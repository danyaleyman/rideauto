"""Публичный rate limit для каталога (slowapi). Отключение: WRA_RATE_LIMIT_PUBLIC_PER_MINUTE=0."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

F = TypeVar("F", bound=Callable[..., Any])


def _client_key(request: Request) -> str:
    try:
        from fastapi_app.config import get_settings

        s = get_settings()
        if s.rate_limit_trust_forwarded_for:
            xff = (request.headers.get("x-forwarded-for") or "").strip()
            if xff:
                return xff.split(",")[0].strip()[:256]
    except Exception:
        pass
    return get_remote_address(request)


def _storage_uri() -> str | None:
    try:
        from fastapi_app.config import get_settings

        s = get_settings()
        raw = (s.rate_limit_redis_uri or "").strip()
        if raw:
            return raw
        return (s.redis_url or "").strip() or None
    except Exception:
        return None


_uri = _storage_uri()
limiter = Limiter(key_func=_client_key, storage_uri=_uri) if _uri else Limiter(key_func=_client_key)


def public_rate_limit() -> Callable[[F], F]:
    """Декоратор для GET каталога; лимит читается при импорте модуля роутера (смена env → рестарт)."""
    from fastapi_app.config import get_settings

    n = int(get_settings().rate_limit_public_per_minute or 0)
    if n <= 0:

        def _noop(f: F) -> F:
            return f

        return _noop
    return limiter.limit(f"{n}/minute")
