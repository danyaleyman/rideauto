#!/usr/bin/env python3
"""Создать минимальную SQLite для E2E (та же схема cars, что в backend/tests/conftest)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: init_e2e_db.py <path.db>", file=sys.stderr)
        sys.exit(1)
    db_path = Path(sys.argv[1]).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DROP TABLE IF EXISTS cars")
        conn.execute(
            """
            CREATE TABLE cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id TEXT NOT NULL,
                data_json TEXT NOT NULL
            )
            """
        )

        def ins(pk: int, car_id: str, payload: dict) -> None:
            conn.execute(
                "INSERT INTO cars (id, car_id, data_json) VALUES (?, ?, ?)",
                (pk, car_id, json.dumps(payload, ensure_ascii=False)),
            )

        base = {
            "data": {
                "mark": "Hyundai",
                "model": "Solaris",
                "price_won": 10000,
                "inner_id": "enc-1",
                "year": "2020",
                "km_age": 50000,
            }
        }
        ins(1, "c1", base)
        similar = {
            "data": {
                "mark": "Hyundai",
                "model": "Accent",
                "price_won": 10500,
                "inner_id": "enc-2",
                "year": "2019",
                "km_age": 60000,
            }
        }
        ins(2, "c2", similar)
        other_mark = {
            "data": {
                "mark": "Kia",
                "model": "Rio",
                "price_won": 11000,
                "inner_id": "enc-3",
                "year": "2021",
                "km_age": 30000,
            }
        }
        ins(3, "c3", other_mark)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
