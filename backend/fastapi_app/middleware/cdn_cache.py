"""
CDN-friendly заголовки для публичных GET:
- Cache-Control: public, max-age, stale-while-revalidate (по типу пути)
- Weak ETag для JSON + If-None-Match → 304
- Удаление Set-Cookie на публичных маршрутах

Персональные префиксы (/api/me, /api/auth, …) не трогаются.
Middleware добавлять после CORSMiddleware, чтобы в ответе уже были CORS-заголовки.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fastapi_app.config import Settings, get_settings

_PRIVATE_PATH_PREFIXES: tuple[str, ...] = (
    "/api/me",
    "/api/auth",
    "/api/favorites",
    "/api/history",
    "/api/subscriptions",
    "/api/checkout",
    "/api/compare",
    "/api/logout",
    "/api/internal",
)


def _is_private_path(path: str) -> bool:
    return any(path.startswith(p) for p in _PRIVATE_PATH_PREFIXES)


def _is_public_cdn_path(path: str) -> bool:
    return path.startswith("/api/") and not _is_private_path(path)


def _cache_control_for_path(path: str, settings: Settings) -> Optional[str]:
    if path in ("/api/search", "/api/cars"):
        return settings.cdn_cc_search
    if path in ("/api/facets", "/api/filters"):
        return settings.cdn_cc_facets
    if path.startswith("/api/car/"):
        return settings.cdn_cc_car
    if path == "/api/health":
        return settings.cdn_cc_health
    if path.startswith("/api/images/"):
        return None
    return None


def _response_has_no_store(headers: MutableHeaders) -> bool:
    cc = (headers.get("cache-control") or "").lower()
    return "no-store" in cc or "private" in cc


def _strip_set_cookie(headers: MutableHeaders) -> None:
    # Starlette MutableHeaders has no clear() in some versions.
    # Deleting the key removes all Set-Cookie header instances.
    if "set-cookie" in headers:
        del headers["set-cookie"]


def _weak_etag(body: bytes) -> str:
    return f'W/"{hashlib.sha256(body).hexdigest()}"'


def _if_none_match_matches(inm: str, etag: str) -> bool:
    inm = (inm or "").strip()
    if not inm:
        return False
    for part in inm.split(","):
        t = part.strip()
        if t == "*" or t == etag:
            return True
    return False


def _copy_headers_skip_body_meta(src: MutableHeaders) -> MutableHeaders:
    out = MutableHeaders()
    skip = frozenset({"content-length", "content-encoding", "transfer-encoding"})
    for k, v in src.items():
        if k.lower() in skip:
            continue
        out.append(k, v)
    return out


class CDNCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.method != "GET":
            return response

        path = request.url.path
        settings = get_settings()
        hdrs: MutableHeaders = response.headers

        if settings.cdn_strip_set_cookie and _is_public_cdn_path(path):
            _strip_set_cookie(hdrs)

        target_cc = _cache_control_for_path(path, settings)
        if target_cc and _is_public_cdn_path(path) and not _response_has_no_store(hdrs):
            hdrs["Cache-Control"] = target_cc

        want_etag = (
            settings.cdn_etag_enabled
            and _is_public_cdn_path(path)
            and response.status_code == 200
            and "application/json" in (hdrs.get("content-type") or "").lower()
        )
        if not want_etag:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        etag = _weak_etag(body)
        inm = request.headers.get("if-none-match", "")
        if _if_none_match_matches(inm, etag):
            out_h = _copy_headers_skip_body_meta(hdrs)
            out_h["ETag"] = etag
            if target_cc:
                out_h["Cache-Control"] = target_cc
            elif not out_h.get("cache-control"):
                out_h["Cache-Control"] = settings.cdn_cc_default_json
            return Response(status_code=304, headers=out_h)

        out_h = MutableHeaders()
        for k, v in hdrs.items():
            out_h.append(k, v)
        out_h["ETag"] = etag
        return Response(
            content=body,
            status_code=response.status_code,
            media_type=hdrs.get("content-type"),
            headers=out_h,
        )
