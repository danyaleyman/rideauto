"""Фикстуры: временная SQLite с таблицей cars (минимальная схема под API)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict

import pytest

from api_server import APP_DB, create_app, _now_iso


def _insert_car(conn: sqlite3.Connection, pk: int, car_id: str, payload: Dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO cars (id, car_id, data_json) VALUES (?, ?, ?)",
        (pk, car_id, json.dumps(payload, ensure_ascii=False)),
    )


@pytest.fixture
def cars_db_path(tmp_path: Path) -> str:
    """Пустая users-схема + cars; строки для /api/similar и /api/health."""
    db = tmp_path / "test_api.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            """
            CREATE TABLE cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id TEXT NOT NULL,
                data_json TEXT NOT NULL
            )
            """
        )
        base = {
            "data": {
                "mark": "Hyundai",
                "model": "Solaris",
                "price_won": 10000,
                "my_price": 1500000,
                "inner_id": "enc-1",
                "year": "2020",
                "km_age": 50000,
            }
        }
        _insert_car(conn, 1, "c1", base)
        similar = {
            "data": {
                "mark": "Hyundai",
                "model": "Accent",
                "price_won": 10500,
                "my_price": 1200000,
                "inner_id": "enc-2",
                "year": "2019",
                "km_age": 60000,
            }
        }
        _insert_car(conn, 2, "c2", similar)
        other_mark = {
            "data": {
                "mark": "Kia",
                "model": "Rio",
                "price_won": 11000,
                "my_price": 1800000,
                "inner_id": "enc-3",
                "year": "2021",
                "km_age": 30000,
            }
        }
        _insert_car(conn, 3, "c3", other_mark)
        conn.commit()
    finally:
        conn.close()
    return str(db.resolve())


@pytest.fixture
def test_app(cars_db_path: str):
    return create_app(cars_db_path)


@pytest.fixture
def auth_headers(test_app):
    """Bearer-токен и строка users/sessions в той же БД, что у test_app."""
    conn = test_app[APP_DB]
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO users (tg_id, username, first_name, last_name, photo_url, raw_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("999001", "tester", "T", "User", None, "{}", now, now),
    )
    uid = conn.execute("SELECT id FROM users WHERE tg_id = ?", ["999001"]).fetchone()["id"]
    token = "test-session-token-wra-01"
    exp = "2099-01-01T00:00:00Z"
    conn.execute(
        """
        INSERT INTO user_sessions (token, user_id, created_at, expires_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (token, uid, now, exp, now),
    )
    conn.commit()
    return {"Authorization": f"Bearer {token}"}
