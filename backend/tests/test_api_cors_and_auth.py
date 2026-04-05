"""CORS preflight и ответы 401 без сессии."""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer


@pytest.mark.asyncio
async def test_cors_preflight_options(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.options(
            "/api/cars",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status == 204
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "GET" in (resp.headers.get("Access-Control-Allow-Methods") or "")


@pytest.mark.asyncio
async def test_get_response_includes_cors_headers(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/health", headers={"Origin": "https://example.com"})
        assert resp.status == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"


@pytest.mark.asyncio
async def test_me_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/me")
        assert resp.status == 401
        data = await resp.json()
        assert data.get("error") == "unauthorized"


@pytest.mark.asyncio
async def test_favorites_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/favorites")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_favorites_post_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.post("/api/favorites", json={"car_id": "c1"})
        assert resp.status == 401


@pytest.mark.asyncio
async def test_favorites_delete_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.delete("/api/favorites/c1")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_history_post_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.post("/api/history", json={"car_id": "c1"})
        assert resp.status == 401


@pytest.mark.asyncio
async def test_history_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/history")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_subscriptions_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/subscriptions")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_subscriptions_post_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.post("/api/subscriptions", json={"name": "x", "filters": {}})
        assert resp.status == 401


@pytest.mark.asyncio
async def test_subscriptions_delete_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.delete("/api/subscriptions/1")
        assert resp.status == 401


@pytest.mark.asyncio
async def test_checkout_without_token_returns_401(test_app):
    async with TestClient(TestServer(test_app)) as client:
        assert (await client.get("/api/checkout")).status == 401
        assert (await client.post("/api/checkout", json={"car_ids": ["c1"]})).status == 401


@pytest.mark.asyncio
async def test_run_subscription_notifications_without_config_returns_503(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.post("/api/subscriptions/run-notifications")
        assert resp.status == 503
        data = await resp.json()
        assert "SUBSCRIPTIONS_ADMIN_KEY" in (data.get("error") or "")
