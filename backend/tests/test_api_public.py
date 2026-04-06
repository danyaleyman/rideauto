"""Публичные эндпоинты без авторизации."""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer


@pytest.mark.asyncio
async def test_health_ok(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/health")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("status") == "ok"


@pytest.mark.asyncio
async def test_health_includes_git_sha_when_env_set(test_app, monkeypatch):
    monkeypatch.setenv("WRA_GIT_SHA", "abc123")
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/health")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("git_sha") == "abc123"


@pytest.mark.asyncio
async def test_version_ok(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/version")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("service") == "prod-encar-api"
        assert "python" in data
        assert resp.headers.get("Cache-Control", "").lower() == "no-store"


@pytest.mark.asyncio
async def test_version_git_sha_from_env(test_app, monkeypatch):
    monkeypatch.setenv("WRA_GIT_SHA", "deadbeef")
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/version")
        data = await resp.json()
        assert data.get("git_sha") == "deadbeef"


@pytest.mark.asyncio
async def test_stats_lists_total(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/stats")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("total") == 3
        assert "listed_today" in data
        assert "date_utc" in data
        assert data.get("korea_listed") == 3
        assert data.get("china_listed") == 0


@pytest.mark.asyncio
async def test_counts_matches_stats(test_app):
    async with TestClient(TestServer(test_app)) as client:
        r_stats = await client.get("/api/stats")
        r_counts = await client.get("/api/counts")
        assert r_stats.status == 200 and r_counts.status == 200
        assert await r_stats.json() == await r_counts.json()


@pytest.mark.asyncio
async def test_sort_meta_options(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/sort")
        assert resp.status == 200
        data = await resp.json()
        opts = data.get("options")
        assert isinstance(opts, list) and len(opts) >= 1
        assert all("value" in o and "title" in o for o in opts)


@pytest.mark.asyncio
async def test_facets_returns_mark_lists(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/facets")
        assert resp.status == 200
        data = await resp.json()
        marks = data.get("marks")
        assert isinstance(marks, list)
        values = {m.get("value") for m in marks if isinstance(m, dict)}
        assert "Hyundai" in values
        assert "Kia" in values


@pytest.mark.asyncio
async def test_cars_first_page(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/cars", params={"page": "1", "per_page": "10"})
        assert resp.status == 200
        data = await resp.json()
        assert isinstance(data.get("result"), list)
        meta = data.get("meta") or {}
        assert meta.get("total") == 3
        assert len(data["result"]) == 3


@pytest.mark.asyncio
async def test_car_by_id_ok(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/car/c1")
        assert resp.status == 200
        data = await resp.json()
        car = data.get("result") or {}
        inner = car.get("data") or {}
        assert inner.get("mark") == "Hyundai"


@pytest.mark.asyncio
async def test_car_by_id_not_found(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/car/unknown-xyz")
        assert resp.status == 404


@pytest.mark.asyncio
async def test_filters_alias_matches_facets(test_app):
    async with TestClient(TestServer(test_app)) as client:
        r_facets = await client.get("/api/facets")
        assert r_facets.status == 200
        r_filters = await client.get("/api/filters")
        assert r_filters.status == 200
        jf, jg = await r_facets.json(), await r_filters.json()
        assert jf == jg


@pytest.mark.asyncio
async def test_compare_returns_cars_by_ids(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/compare", params={"ids": "c1,c2"})
        assert resp.status == 200
        data = await resp.json()
        res = data.get("result") or []
        assert len(res) == 2
        marks = {x.get("title", "") for x in res}
        assert any("Hyundai" in t for t in marks)


@pytest.mark.asyncio
async def test_compare_empty_ids(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/compare")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("result") == []


@pytest.mark.asyncio
async def test_similar_returns_json_without_programming_error(test_app):
    """Регрессия: число плейсхолдеров SQL и параметров в _similar_rows."""
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/similar", params={"car_id": "c1", "limit": "5"})
        assert resp.status == 200
        data = await resp.json()
        assert isinstance(data.get("result"), list)
        assert "meta" in data
