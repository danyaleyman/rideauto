from __future__ import annotations

from fastapi import Request
from meilisearch import Client

from fastapi_app.cache import CacheBackend
from fastapi_app.config import Settings, get_settings


def get_settings_dep() -> Settings:
    return get_settings()


async def get_pg_pool(request: Request):
    return request.app.state.pg_pool


def get_meilisearch(request: Request) -> Client:
    return request.app.state.meili


def get_cache_backend(request: Request) -> CacheBackend:
    return request.app.state.cache
