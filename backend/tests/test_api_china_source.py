"""API: Корея (encar) vs Китай (только Dongchedi); отдельная БД через create_app(..., china_db_path=)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from api_server import create_app


@pytest.fixture
def cars_db_mixed(tmp_path: Path) -> str:
    """Одна БД: Encar + Dongchedi (без che168)."""
    db = tmp_path / "mix.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        CREATE TABLE cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id TEXT NOT NULL,
            data_json TEXT NOT NULL
        )
        """
    )
    enc = {"data": {"mark": "Hyundai", "model": "Solaris", "inner_id": "e1", "my_price": 1000}}
    conn.execute(
        "INSERT INTO cars (car_id, data_json) VALUES (?, ?)",
        ("enc-1", json.dumps(enc, ensure_ascii=False)),
    )
    dcd = {
        "data": {
            "source": "dongchedi",
            "mark": "宝马",
            "model": "DCD",
            "inner_id": "7",
            "my_price": 600000,
        }
    }
    conn.execute(
        "INSERT INTO cars (car_id, data_json) VALUES (?, ?)",
        ("dongchedi-7", json.dumps(dcd, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    return str(db.resolve())


@pytest.fixture
def dual_korea_china_paths(tmp_path: Path) -> tuple[str, str]:
    kdb = tmp_path / "korea.db"
    cdb = tmp_path / "china.db"
    kc = sqlite3.connect(str(kdb))
    kc.execute(
        "CREATE TABLE cars (id INTEGER PRIMARY KEY AUTOINCREMENT, car_id TEXT NOT NULL, data_json TEXT NOT NULL)"
    )
    enc = {"data": {"mark": "Kia", "model": "Rio", "inner_id": "k1", "my_price": 2000}}
    kc.execute("INSERT INTO cars (car_id, data_json) VALUES (?, ?)", ("enc-k1", json.dumps(enc)))
    kc.commit()
    kc.close()
    cc = sqlite3.connect(str(cdb))
    cc.execute(
        "CREATE TABLE cars (id INTEGER PRIMARY KEY AUTOINCREMENT, car_id TEXT NOT NULL, data_json TEXT NOT NULL)"
    )
    dcd = {
        "data": {
            "source": "dongchedi",
            "mark": "比亚迪",
            "model": "Han",
            "inner_id": "88",
            "my_price": 3000000,
        }
    }
    cc.execute(
        "INSERT INTO cars (car_id, data_json) VALUES (?, ?)",
        ("dongchedi-88", json.dumps(dcd, ensure_ascii=False)),
    )
    cc.commit()
    cc.close()
    return str(kdb.resolve()), str(cdb.resolve())


@pytest.mark.asyncio
async def test_cars_source_che168_returns_empty(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/cars", params={"page": "1", "per_page": "20", "source": "che168"})
        assert r.status == 200
        data = await r.json()
        assert (data.get("result") or []) == []


@pytest.mark.asyncio
async def test_cars_source_encar_excludes_dongchedi(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/cars", params={"page": "1", "per_page": "20", "source": "encar"})
        assert r.status == 200
        data = await r.json()
        ids = {x.get("id") for x in (data.get("result") or [])}
        assert ids == {"enc-1"}


@pytest.mark.asyncio
async def test_cars_source_dongchedi_only(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/cars", params={"page": "1", "per_page": "20", "source": "dongchedi"})
        assert r.status == 200
        data = await r.json()
        ids = {x.get("id") for x in (data.get("result") or [])}
        assert ids == {"dongchedi-7"}


@pytest.mark.asyncio
async def test_cars_source_china_is_dongchedi_only(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/cars", params={"page": "1", "per_page": "20", "source": "china"})
        assert r.status == 200
        data = await r.json()
        ids = {x.get("id") for x in (data.get("result") or [])}
        assert ids == {"dongchedi-7"}


@pytest.mark.asyncio
async def test_cars_region_china_without_source_is_dongchedi(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/cars", params={"page": "1", "per_page": "20", "region": "china"})
        assert r.status == 200
        data = await r.json()
        ids = {x.get("id") for x in (data.get("result") or [])}
        assert ids == {"dongchedi-7"}


@pytest.mark.asyncio
async def test_cars_region_korea_without_source_is_encar(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/cars", params={"page": "1", "per_page": "20", "region": "korea"})
        assert r.status == 200
        data = await r.json()
        ids = {x.get("id") for x in (data.get("result") or [])}
        assert ids == {"enc-1"}


@pytest.mark.asyncio
async def test_facets_che168_empty(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/facets", params={"source": "che168"})
        assert r.status == 200
        data = await r.json()
        assert (data.get("marks") or []) == []


@pytest.mark.asyncio
async def test_facets_respects_source_dongchedi(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/facets", params={"source": "dongchedi"})
        assert r.status == 200
        data = await r.json()
        marks = {m.get("value") for m in (data.get("marks") or []) if isinstance(m, dict)}
        assert "宝马" in marks


@pytest.mark.asyncio
async def test_china_queries_use_separate_db(dual_korea_china_paths: tuple[str, str]):
    korea_p, china_p = dual_korea_china_paths
    app = create_app(korea_p, china_db_path=china_p)
    async with TestClient(TestServer(app)) as client:
        r_k = await client.get("/api/cars", params={"page": "1", "per_page": "20", "source": "encar"})
        assert r_k.status == 200
        jk = await r_k.json()
        assert {x.get("id") for x in (jk.get("result") or [])} == {"enc-k1"}

        r_c = await client.get("/api/cars", params={"page": "1", "per_page": "20", "region": "china"})
        assert r_c.status == 200
        jc = await r_c.json()
        assert {x.get("id") for x in (jc.get("result") or [])} == {"dongchedi-88"}

        st = await client.get("/api/stats")
        assert st.status == 200
        js = await st.json()
        assert js.get("korea_listed") == 1
        assert js.get("china_listed") == 1
