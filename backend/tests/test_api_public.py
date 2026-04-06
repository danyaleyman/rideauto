"""Публичные эндпоинты без авторизации."""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

import api_server


@pytest.mark.asyncio
async def test_health_ok(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/health")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("status") == "ok"
        assert data.get("china_catalog_db") is False


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
async def test_stats_etag_304_when_if_none_match(test_app):
    async with TestClient(TestServer(test_app)) as client:
        r1 = await client.get("/api/stats")
        assert r1.status == 200
        etag = r1.headers.get("ETag")
        assert etag and etag.startswith('W/"md5-')
        r2 = await client.get("/api/stats", headers={"If-None-Match": etag})
        assert r2.status == 304
        assert r2.headers.get("ETag") == etag
        assert await r2.read() == b""


@pytest.mark.asyncio
async def test_health_deep_includes_catalog_probe(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/health", params={"deep": "1"})
        assert resp.status == 200
        data = await resp.json()
        probe = data.get("catalog_db")
        assert isinstance(probe, dict)
        assert probe.get("readable") is True
        assert int(probe.get("cars_rows") or 0) >= 3


@pytest.mark.asyncio
async def test_sitemap_index_xml_contains_pages_and_catalog(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/sitemap/index.xml")
        assert resp.status == 200
        text = await resp.text()
        assert "sitemap-pages.xml" in text
        assert "catalog.xml?part=1" in text


@pytest.mark.asyncio
async def test_cars_cursor_price_high_matches_offset(test_app):
    async with TestClient(TestServer(test_app)) as client:
        r1 = await client.get("/api/cars", params={"page": "1", "per_page": "2", "sort": "price_high"})
        assert r1.status == 200
        j1 = await r1.json()
        cur = (j1.get("meta") or {}).get("next_cursor")
        assert cur
        r2c = await client.get("/api/cars", params={"cursor": cur, "page": "2", "per_page": "2", "sort": "price_high"})
        r2p = await client.get("/api/cars", params={"page": "2", "per_page": "2", "sort": "price_high"})
        assert r2c.status == 200 and r2p.status == 200
        jc, jp = await r2c.json(), await r2p.json()
        assert jc.get("result") == jp.get("result")


@pytest.mark.asyncio
async def test_cars_cursor_second_page_matches_offset(test_app):
    async with TestClient(TestServer(test_app)) as client:
        r1 = await client.get("/api/cars", params={"page": "1", "per_page": "2", "sort": "year_new"})
        assert r1.status == 200
        j1 = await r1.json()
        cur = (j1.get("meta") or {}).get("next_cursor")
        assert cur
        r2c = await client.get("/api/cars", params={"cursor": cur, "page": "2", "per_page": "2", "sort": "year_new"})
        r2p = await client.get("/api/cars", params={"page": "2", "per_page": "2", "sort": "year_new"})
        assert r2c.status == 200 and r2p.status == 200
        jc, jp = await r2c.json(), await r2p.json()
        assert jc.get("result") == jp.get("result")


@pytest.mark.asyncio
async def test_html_car_page_injects_title(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/html/car/c1")
        assert resp.status == 200
        html = await resp.text()
        assert "Hyundai" in html or "Solaris" in html
        assert "application/ld+json" in html


@pytest.mark.asyncio
async def test_html_car_page_404_has_noindex(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/html/car/does-not-exist-xyz")
        assert resp.status == 404
        html = await resp.text()
        assert "noindex" in html.lower()


@pytest.mark.asyncio
async def test_prometheus_metrics_disabled_by_default(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/metrics")
        assert resp.status == 404


@pytest.mark.asyncio
async def test_sitemap_catalog_xml_lists_detail_urls(test_app):
    async with TestClient(TestServer(test_app)) as client:
        resp = await client.get("/api/sitemap/catalog.xml")
        assert resp.status == 200
        assert resp.headers.get("Content-Type", "").lower().startswith("application/xml")
        text = await resp.text()
        assert "<urlset" in text
        assert "https://rideauto.ru/detail/c3" in text
        assert "https://rideauto.ru/detail/c1" in text


@pytest.mark.asyncio
async def test_sitemap_catalog_xml_304_with_if_none_match(test_app):
    async with TestClient(TestServer(test_app)) as client:
        r1 = await client.get("/api/sitemap/catalog.xml")
        etag = r1.headers.get("ETag")
        assert etag
        r2 = await client.get("/api/sitemap/catalog.xml", headers={"If-None-Match": etag})
        assert r2.status == 304


@pytest.mark.asyncio
async def test_cars_link_header_next_page(test_app):
    async with TestClient(TestServer(test_app)) as client:
        r = await client.get("/api/cars", params={"page": "1", "per_page": "2"})
        assert r.status == 200
        link = r.headers.get("Link") or ""
        assert 'rel="next"' in link
        assert "page=2" in link


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
        cc = resp.headers.get("Cache-Control", "").lower()
        assert "stale-while-revalidate" in cc


@pytest.mark.asyncio
async def test_facets_memo_calls_heavy_sql_once(test_app, cars_db_path, monkeypatch):
    calls = {"n": 0}
    orig = api_server._facets_catalog_sync

    def wrapped(db_path: str, q: dict):
        calls["n"] += 1
        return orig(db_path, q)

    monkeypatch.setattr(api_server, "_facets_catalog_sync", wrapped)
    with api_server._FACETS_CACHE_LOCK:
        api_server._FACETS_RESULT_CACHE.clear()
    async with TestClient(TestServer(test_app)) as client:
        r1 = await client.get("/api/facets")
        r2 = await client.get("/api/facets")
        assert r1.status == 200 and r2.status == 200
        assert await r1.json() == await r2.json()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_china_market_empty_db_fast_cars_and_facets(test_app):
    """Без строк Dongchedi в БД: китайский каталог и фасеты — пусто, без тяжёлого CTE."""
    async with TestClient(TestServer(test_app)) as client:
        r1 = await client.get(
            "/api/cars",
            params={"region": "china", "source": "china", "page": "1", "per_page": "12"},
        )
        assert r1.status == 200
        j1 = await r1.json()
        assert (j1.get("meta") or {}).get("total") == 0
        assert j1.get("result") == []
        r2 = await client.get("/api/facets", params={"region": "china", "source": "china"})
        assert r2.status == 200
        j2 = await r2.json()
        assert j2.get("marks") == []
        assert j2.get("models") == []


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
async def test_cars_deep_page_without_cursor_rejected_for_anon(test_app):
    async with TestClient(TestServer(test_app)) as client:
        r = await client.get("/api/cars", params={"page": "100", "per_page": "12"})
        assert r.status == 400
        j = await r.json()
        assert j.get("error") == "deep_pagination_requires_cursor"


@pytest.mark.asyncio
async def test_cars_deep_page_allowed_when_guard_disabled(test_app, monkeypatch):
    monkeypatch.setenv("WRA_CATALOG_MAX_PAGE_OFFSET_ANON", "-1")
    async with TestClient(TestServer(test_app)) as client:
        r = await client.get("/api/cars", params={"page": "100", "per_page": "12"})
        assert r.status == 200


@pytest.mark.asyncio
async def test_health_deep_includes_wal_fields_when_present(test_app, cars_db_path, monkeypatch):
    monkeypatch.setenv("WRA_HEALTH_DEEP", "1")
    from pathlib import Path

    wal = Path(str(cars_db_path) + "-wal")
    wal.write_bytes(b"")
    try:
        async with TestClient(TestServer(test_app)) as client:
            resp = await client.get("/api/health")
            assert resp.status == 200
            data = await resp.json()
            probe = data.get("catalog_db") or {}
            assert probe.get("wal_bytes") is not None
    finally:
        try:
            wal.unlink()
        except OSError:
            pass


@pytest.mark.asyncio
async def test_prometheus_metrics_includes_p95(test_app, monkeypatch):
    monkeypatch.setenv("WRA_PROMETHEUS_METRICS", "1")
    with api_server._METRICS_LOCK:
        api_server._METRIC_DURATION_SAMPLES.clear()
        api_server._METRIC_DURATION_MS_SUM.clear()
        api_server._METRIC_DURATION_MS_COUNT.clear()
    async with TestClient(TestServer(test_app)) as client:
        assert (await client.get("/api/cars", params={"page": "1", "per_page": "5"})).status == 200
        resp = await client.get("/api/metrics")
        assert resp.status == 200
        body = await resp.text()
    assert 'wra_http_request_duration_ms_p95{route_group="cars"}' in body


@pytest.mark.asyncio
async def test_cars_slim_page1_memo_calls_sql_once(test_app, monkeypatch):
    calls = {"n": 0}
    orig = api_server._cars_catalog_sync

    def wrapped(db_path: str, query: dict, *, slim: bool):
        calls["n"] += 1
        return orig(db_path, query, slim=slim)

    monkeypatch.setattr(api_server, "_cars_catalog_sync", wrapped)
    with api_server._CATALOG_LIST_CACHE_LOCK:
        api_server._CATALOG_LIST_CACHE.clear()
    async with TestClient(TestServer(test_app)) as client:
        r1 = await client.get("/api/cars", params={"page": "1", "per_page": "10"})
        r2 = await client.get("/api/cars", params={"page": "1", "per_page": "10"})
        assert r1.status == 200 and r2.status == 200
        assert await r1.json() == await r2.json()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_cars_full_mode_bypasses_list_cache(test_app, monkeypatch):
    calls = {"n": 0}
    orig = api_server._cars_catalog_sync

    def wrapped(db_path: str, query: dict, *, slim: bool):
        calls["n"] += 1
        return orig(db_path, query, slim=slim)

    monkeypatch.setattr(api_server, "_cars_catalog_sync", wrapped)
    with api_server._CATALOG_LIST_CACHE_LOCK:
        api_server._CATALOG_LIST_CACHE.clear()
    async with TestClient(TestServer(test_app)) as client:
        await client.get("/api/cars", params={"page": "1", "per_page": "10", "full": "1"})
        await client.get("/api/cars", params={"page": "1", "per_page": "10", "full": "1"})
    assert calls["n"] == 2


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
