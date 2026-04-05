"""API filter source=che168 / encar."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from api_server import create_app


@pytest.fixture
def cars_db_mixed(tmp_path: Path) -> str:
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
    ch = {
        "data": {
            "source": "che168",
            "mark": "中国二手车",
            "model": "Test",
            "inner_id": "99",
            "my_price": 500000,
        }
    }
    conn.execute(
        "INSERT INTO cars (car_id, data_json) VALUES (?, ?)",
        ("enc-1", json.dumps(enc, ensure_ascii=False)),
    )
    conn.execute(
        "INSERT INTO cars (car_id, data_json) VALUES (?, ?)",
        ("che168-99", json.dumps(ch, ensure_ascii=False)),
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


@pytest.mark.asyncio
async def test_cars_source_che168_only(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/cars", params={"page": "1", "per_page": "20", "source": "che168"})
        assert r.status == 200
        data = await r.json()
        ids = {x.get("id") for x in (data.get("result") or [])}
        assert ids == {"che168-99"}


@pytest.mark.asyncio
async def test_cars_source_encar_excludes_che168(cars_db_mixed: str):
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
async def test_facets_respects_source_che168(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/facets", params={"source": "che168"})
        assert r.status == 200
        data = await r.json()
        marks = {m.get("value") for m in (data.get("marks") or []) if isinstance(m, dict)}
        assert "中国二手车" in marks


@pytest.mark.asyncio
async def test_facets_respects_source_dongchedi(cars_db_mixed: str):
    app = create_app(cars_db_mixed)
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/api/facets", params={"source": "dongchedi"})
        assert r.status == 200
        data = await r.json()
        marks = {m.get("value") for m in (data.get("marks") or []) if isinstance(m, dict)}
        assert "宝马" in marks
