"""Сессия: избранное и история с валидным Bearer."""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer


@pytest.mark.asyncio
async def test_me_ok_with_token(test_app, auth_headers):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/me", headers=auth_headers)
        assert resp.status == 200
        data = await resp.json()
        u = data.get("user") or {}
        assert u.get("tg_id") == "999001"
        assert u.get("username") == "tester"


@pytest.mark.asyncio
async def test_favorites_empty_then_add(test_app, auth_headers):
    async with TestClient(TestServer(test_app)) as client:
        r0 = await client.get("/api/favorites", headers=auth_headers)
        assert r0.status == 200
        assert (await r0.json()).get("result") == []
        r1 = await client.post("/api/favorites", headers=auth_headers, json={"car_id": "c1"})
        assert r1.status == 200
        assert (await r1.json()).get("ok") is True
        r2 = await client.get("/api/favorites", headers=auth_headers)
        rows = (await r2.json()).get("result") or []
        assert len(rows) == 1
        assert rows[0].get("car_id") == "c1"


@pytest.mark.asyncio
async def test_history_post_and_list(test_app, auth_headers):
    async with TestClient(TestServer(test_app)) as client:
        r1 = await client.post("/api/history", headers=auth_headers, json={"car_id": "c2"})
        assert r1.status == 200
        r2 = await client.get("/api/history", headers=auth_headers, params={"limit": "10"})
        assert r2.status == 200
        rows = (await r2.json()).get("result") or []
        assert any(r.get("car_id") == "c2" for r in rows)
