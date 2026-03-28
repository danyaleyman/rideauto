#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Очистка локального хранилища скрапера: таблица cars + checkpoint (собранные id / pending).

Пути по умолчанию от корня репозитория (как в scraper_config.yaml).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def clear_sqlite_table(db_path: Path, table: str) -> int:
    if not db_path.is_file():
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(f"DELETE FROM {table}")
        conn.commit()
        return cur.rowcount if cur.rowcount is not None else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def reset_checkpoint(db_path: Path) -> None:
    if not db_path.is_file():
        return
    conn = sqlite3.connect(str(db_path))
    try:
        for tbl in ("pending_ids", "collected_ids", "state"):
            try:
                conn.execute(f"DELETE FROM {tbl}")
            except sqlite3.OperationalError:
                pass
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Очистить encar_cars.db и scraper_checkpoint.db")
    p.add_argument("--repo", type=Path, default=_REPO)
    p.add_argument(
        "--cars-db",
        type=Path,
        default=None,
        help="Путь к SQLite с объявлениями (по умолчанию repo/encar_cars.db)",
    )
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Путь к checkpoint (по умолчанию repo/scraper_checkpoint.db)",
    )
    args = p.parse_args()
    repo = args.repo.resolve()
    cars_db = args.cars_db or (repo / "encar_cars.db")
    cp = args.checkpoint or (repo / "scraper_checkpoint.db")

    n = clear_sqlite_table(cars_db, "cars")
    print(f"Deleted from cars: {n} rows in {cars_db}")
    reset_checkpoint(cp)
    print(f"Checkpoint cleared: {cp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
