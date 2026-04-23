"""
Запуск (из каталога `backend`, с активированным venv):

  uvicorn fastapi_app.main:app --host 127.0.0.1 --port 8080

Переменные окружения: см. `fastapi_app.config.Settings` (префикс WRA_).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from meilisearch import Client

from fastapi_app.cache import NoOpCache
from fastapi_app.config import get_settings
from fastapi_app.metrics.prometheus import metrics_payload
from fastapi_app.middleware.cdn_cache import CDNCacheMiddleware
from fastapi_app.middleware.prometheus_http import PrometheusHTTPMiddleware
from fastapi_app.redis_cache import RedisJSONCache, close_redis_client, create_redis_client
from fastapi_app.routers import (
    cache_invalidate,
    car,
    catalog_stats,
    facets,
    images,
    lead,
    search,
    translate,
    web_vitals,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    app.state.settings = settings
    prefix = settings.redis_cache_prefix.strip().rstrip(":")
    app.state.cache_key_prefix = prefix
    rurl = (settings.redis_url or "").strip()
    if rurl:
        app.state.redis = create_redis_client(rurl)
        app.state.cache = RedisJSONCache(app.state.redis, key_prefix=prefix)
    else:
        app.state.redis = None
        app.state.cache = NoOpCache()
    app.state.pg_pool = await asyncpg.create_pool(
        settings.pg_dsn,
        min_size=2,
        max_size=20,
        command_timeout=120,
    )
    app.state.meili = Client(
        settings.meilisearch_url,
        settings.meilisearch_key or None,
    )
    yield
    await app.state.pg_pool.close()
    await close_redis_client(getattr(app.state, "redis", None))


def create_app() -> FastAPI:
    app = FastAPI(title="Prod Encar API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CDNCacheMiddleware)
    app.add_middleware(PrometheusHTTPMiddleware)
    app.include_router(search.router, prefix="/api")
    app.include_router(catalog_stats.router, prefix="/api")
    app.include_router(car.router, prefix="/api")
    app.include_router(facets.router, prefix="/api")
    app.include_router(cache_invalidate.router, prefix="/api")
    app.include_router(images.router, prefix="/api")
    app.include_router(web_vitals.router, prefix="/api")
    app.include_router(lead.router, prefix="/api")
    app.include_router(translate.router, prefix="/api")

    @app.get("/api/health")
    async def health(request: Request):
        return {
            "status": "ok",
            "service": "prod-encar-fastapi",
            "redis_cache": getattr(request.app.state, "redis", None) is not None,
        }

    def _metrics_path() -> str:
        p = (get_settings().metrics_path or "/metrics").strip()
        return p if p.startswith("/") else f"/{p}"

    async def prometheus_metrics() -> Response:
        if not get_settings().metrics_enabled:
            raise HTTPException(status_code=404, detail="metrics disabled")
        body, ctype = metrics_payload()
        return Response(content=body, media_type=ctype)

    app.add_api_route(_metrics_path(), prometheus_metrics, methods=["GET"], include_in_schema=False)

    return app


app = create_app()
