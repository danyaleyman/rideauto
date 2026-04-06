"""Логирование, X-Request-Id, rate limit."""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

import api_server


@pytest.fixture(autouse=True)
def _clear_rate_buckets():
    api_server._RATE_BUCKETS.clear()
    yield
    api_server._RATE_BUCKETS.clear()


@pytest.mark.asyncio
async def test_x_request_id_echoed_when_valid(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/health", headers={"X-Request-Id": "client-req-1-abcd"})
        assert resp.status == 200
        assert resp.headers.get("X-Request-Id") == "client-req-1-abcd"


@pytest.mark.asyncio
async def test_x_request_id_generated_when_missing(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/health")
        assert resp.status == 200
        rid = resp.headers.get("X-Request-Id")
        assert rid and len(rid) >= 8


@pytest.mark.asyncio
async def test_get_facets_rate_limit_returns_429(test_app, monkeypatch):
    monkeypatch.setenv("WRA_RATE_LIMIT_GET_FACETS_PER_MINUTE", "2")
    async with TestClient(TestServer(test_app)) as client:
        assert (await client.get("/api/facets")).status == 200
        assert (await client.get("/api/facets")).status == 200
        r3 = await client.get("/api/facets")
        assert r3.status == 429


@pytest.mark.asyncio
async def test_get_cars_rate_limit_returns_429(test_app, monkeypatch):
    monkeypatch.setenv("WRA_RATE_LIMIT_GET_CARS_PER_MINUTE", "2")
    async with TestClient(TestServer(test_app)) as client:
        assert (await client.get("/api/cars", params={"page": "1", "per_page": "5"})).status == 200
        assert (await client.get("/api/cars", params={"page": "1", "per_page": "5"})).status == 200
        r3 = await client.get("/api/cars", params={"page": "1", "per_page": "5"})
        assert r3.status == 429
        body = await r3.json()
        assert body.get("error") == "rate_limit"


@pytest.mark.asyncio
async def test_security_headers_on_json_route(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/health")
        assert resp.status == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"


@pytest.mark.asyncio
async def test_post_rate_limit_returns_429(test_app, monkeypatch):
    monkeypatch.setenv("WRA_RATE_LIMIT_POST_PER_MINUTE", "2")
    async with TestClient(TestServer(test_app)) as client:
        # logout — дешёвый POST без зависимости от TELEGRAM_BOT_TOKEN
        assert (await client.post("/api/logout")).status == 200
        assert (await client.post("/api/logout")).status == 200
        r3 = await client.post("/api/logout")
        assert r3.status == 429
        body = await r3.json()
        assert body.get("error") == "rate_limit"
        assert r3.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_telegram_auth_separate_limit(test_app, monkeypatch):
    monkeypatch.setenv("WRA_RATE_LIMIT_POST_PER_MINUTE", "0")
    monkeypatch.setenv("WRA_RATE_LIMIT_TELEGRAM_AUTH_PER_MINUTE", "1")
    async with TestClient(TestServer(test_app)) as client:
        assert (await client.post("/api/auth/telegram", json={})).status in (400, 401, 403, 503)
        r2 = await client.post("/api/auth/telegram", json={})
        assert r2.status == 429
