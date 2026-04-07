"""Middleware: latency и счётчики HTTP для Prometheus."""

from __future__ import annotations

import time

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request

from fastapi_app.config import get_settings
from fastapi_app.metrics.prometheus import normalize_path_group, observe_http


class PrometheusHTTPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        settings = get_settings()
        if not settings.metrics_enabled:
            return await call_next(request)
        path = request.url.path
        if path == (settings.metrics_path or "/metrics"):
            return await call_next(request)
        method = request.method
        path_group = normalize_path_group(path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except StarletteHTTPException as e:
            elapsed = time.perf_counter() - start
            observe_http(method, path_group, e.status_code, elapsed)
            raise
        except Exception:
            elapsed = time.perf_counter() - start
            observe_http(method, path_group, 500, elapsed)
            raise
        elapsed = time.perf_counter() - start
        observe_http(method, path_group, response.status_code, elapsed)
        return response
