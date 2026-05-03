from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from fastapi_app.cache import NoOpCache
from fastapi_app.routers import search as search_router
from fastapi_app.schemas.api import SimilarMeta, SimilarResponse


def _fake_request(*, meili=None):
    state = SimpleNamespace(
        pg_pool=object(),
        meili=meili,
        cache=NoOpCache(),
        cache_key_prefix="wra:test",
    )
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app)


class _FakeIndex:
    def __init__(self, hits):
        self._hits = hits

    def search(self, _q, _opts):
        return {
            "hits": self._hits,
            "estimatedTotalHits": len(self._hits),
            "processingTimeMs": 1,
        }


class _FakeMeili:
    def __init__(self, hits):
        self._hits = hits

    def index(self, _name):
        return _FakeIndex(self._hits)


@pytest.mark.asyncio
async def test_similar_core_404_when_car_missing(monkeypatch):
    async def fake_cur(_pool, _car_id):
        return None

    monkeypatch.setattr(search_router, "fetch_car_any_id", fake_cur)
    req = _fake_request(meili=_FakeMeili([]))

    with pytest.raises(HTTPException) as ex:
        await search_router._similar_cars(req, "missing", 8)
    assert ex.value.status_code == 404


@pytest.mark.asyncio
async def test_similar_core_empty_when_mark_absent(monkeypatch):
    async def fake_cur(_pool, _car_id):
        return {"id": "c1", "data": {"model": "Solaris"}}

    monkeypatch.setattr(search_router, "fetch_car_any_id", fake_cur)
    req = _fake_request(meili=_FakeMeili([]))
    body = await search_router._similar_cars(req, "c1", 8)

    assert body.result == []
    assert body.meta.car_id == "c1"
    assert body.meta.total_candidates == 0


@pytest.mark.asyncio
async def test_similar_core_excludes_self_and_clamps_result(monkeypatch):
    async def fake_cur(_pool, _car_id):
        return {"id": "c1", "data": {"mark": "Hyundai", "model": "Solaris"}}

    async def fake_by_ids(_pool, ids):
        out = {}
        for cid in ids:
            out[cid] = {"id": cid, "data": {"mark": "Hyundai", "model": "X"}}
        return out

    monkeypatch.setattr(search_router, "fetch_car_any_id", fake_cur)
    monkeypatch.setattr(search_router, "fetch_cars_by_ids", fake_by_ids)

    hits = [
        {"id": "c1"},  # self -> skip
        {"id": "c2"},
        {"id": "c2"},  # dup -> skip
        {"id": "c3"},
        {"id": "c4"},
    ]
    req = _fake_request(meili=_FakeMeili(hits))
    body = await search_router._similar_cars(req, "c1", 2)

    assert [x.id for x in body.result] == ["c2", "c3"]
    assert body.meta.limit == 2
    assert body.meta.total_candidates >= 1


@pytest.mark.asyncio
async def test_similar_route_clamps_limit_to_24(monkeypatch):
    called = {"limit": None, "car_id": None}

    async def fake_similar(request, car_id: str, limit: int):
        called["limit"] = limit
        called["car_id"] = car_id
        return SimilarResponse(
            result=[],
            meta=SimilarMeta(car_id=car_id, limit=limit, total_candidates=0),
        )

    monkeypatch.setattr(search_router, "_similar_cars", fake_similar)
    req = _fake_request(meili=_FakeMeili([]))

    payload = await search_router.similar("c1", req, limit=999)
    assert called["car_id"] == "c1"
    assert called["limit"] == 24
    assert payload["meta"]["limit"] == 24
