"""Saver: SQLite, chunked JSON, PostgreSQL (upsert как в migrate_sqlite_to_postgres)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import psycopg2  # noqa: F401


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_pg_migrate():
    path = _repo_root() / "infrastructure" / "postgresql" / "migrate_sqlite_to_postgres.py"
    spec = importlib.util.spec_from_file_location("wra_pg_migrate_encar", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load migrate module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SQLiteStorage:
    def __init__(self, path: str, store_raw: bool = False):
        self.path = path
        self.store_raw = store_raw
        self.conn: Optional[sqlite3.Connection] = None
        self._seq = 0

    def connect(self) -> None:
        self.conn = sqlite3.connect(self.path, timeout=120.0)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id TEXT UNIQUE NOT NULL,
                data_json TEXT NOT NULL,
                raw_json TEXT,
                created_at TEXT
            )
        """
        )
        self.conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_wra_cars_car_id_id ON cars(car_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_wra_data_mark ON cars(json_extract(data_json, '$.data.mark'));
            CREATE INDEX IF NOT EXISTS idx_wra_data_model ON cars(json_extract(data_json, '$.data.model'));
            CREATE INDEX IF NOT EXISTS idx_wra_data_mark_model ON cars(
                json_extract(data_json, '$.data.mark'),
                json_extract(data_json, '$.data.model')
            );
            CREATE INDEX IF NOT EXISTS idx_wra_data_color ON cars(json_extract(data_json, '$.data.color'));
            CREATE INDEX IF NOT EXISTS idx_wra_data_my_price ON cars(
                CAST(json_extract(data_json, '$.data.my_price') AS REAL)
            );
            CREATE INDEX IF NOT EXISTS idx_wra_data_km_age ON cars(
                CAST(json_extract(data_json, '$.data.km_age') AS INTEGER)
            );
            CREATE INDEX IF NOT EXISTS idx_wra_data_year ON cars(
                CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER)
            );
            CREATE INDEX IF NOT EXISTS idx_wra_data_ym ON cars(
                (CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.yearMonth'), json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER) * 12 +
                CASE WHEN LENGTH(COALESCE(json_extract(data_json, '$.data.yearMonth'), '')) >= 6
                THEN CAST(SUBSTR(json_extract(data_json, '$.data.yearMonth'), 5, 2) AS INTEGER) - 1 ELSE 0 END)
            );
            CREATE INDEX IF NOT EXISTS idx_wra_data_power ON cars(
                COALESCE(
                    CAST(json_extract(data_json, '$.data.power') AS INTEGER),
                    CAST(json_extract(data_json, '$.data.hp') AS INTEGER),
                    CAST(json_extract(data_json, '$.power') AS INTEGER)
                )
            );
            CREATE INDEX IF NOT EXISTS idx_wra_data_displacement ON cars(
                CAST(json_extract(data_json, '$.data.displacement') AS INTEGER)
            );
            CREATE INDEX IF NOT EXISTS idx_wra_ins_cases ON cars(
                COALESCE(json_array_length(json_extract(data_json, '$.data.extra.record_open.accidents')), 0)
            );
        """
        )
        self.conn.commit()

    def save_car(self, car: dict, car_id: str) -> None:
        if not self.conn:
            return
        data_json = json.dumps(car, ensure_ascii=False)
        raw_json = (
            json.dumps(car.get("_raw", {}), ensure_ascii=False) if self.store_raw and car.get("_raw") else None
        )
        created = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO cars (car_id, data_json, raw_json, created_at) VALUES (?, ?, ?, ?)",
            (car_id, data_json, raw_json, created),
        )
        self.conn.commit()

    def count_cars(self) -> int:
        if not self.conn:
            return 0
        row = self.conn.execute("SELECT COUNT(*) FROM cars").fetchone()
        return int(row[0] or 0) if row else 0

    def get_car_ids_sample(self, limit: int = 500) -> List[str]:
        if not self.conn:
            return []
        rows = self.conn.execute("SELECT car_id FROM cars ORDER BY RANDOM() LIMIT ?", (limit,)).fetchall()
        return [r[0] for r in rows]

    def delete_car(self, car_id: str) -> None:
        if not self.conn:
            return
        self.conn.execute("DELETE FROM cars WHERE car_id = ?", (car_id,))
        self.conn.commit()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None


class ChunkedJSONStorage:
    def __init__(self, dir_path: str, cars_per_file: int = 1000, store_raw: bool = False):
        self.dir_path = Path(dir_path)
        self.cars_per_file = cars_per_file
        self.store_raw = store_raw
        self.current_chunk: List[dict] = []
        self.chunk_index = 0
        self.dir_path.mkdir(parents=True, exist_ok=True)
        self._find_next_chunk_index()

    def _find_next_chunk_index(self) -> None:
        existing = list(self.dir_path.glob("cars_*.json"))
        if not existing:
            self.chunk_index = 0
            return
        indices = []
        for p in existing:
            try:
                n = int(p.stem.split("_")[1])
                indices.append(n)
            except (IndexError, ValueError):
                pass
        self.chunk_index = max(indices, default=0)

    def save_car(self, car: dict, car_id: str) -> None:
        out = dict(car)
        if self.store_raw and car.get("_raw"):
            out["_raw"] = car["_raw"]
        self.current_chunk.append(out)
        if len(self.current_chunk) >= self.cars_per_file:
            self._flush_chunk()

    def _flush_chunk(self) -> None:
        if not self.current_chunk:
            return
        self.chunk_index += 1
        path = self.dir_path / f"cars_{self.chunk_index:05d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"result": self.current_chunk, "meta": {"chunk": self.chunk_index}}, f, ensure_ascii=False, indent=2)
        self.current_chunk = []

    def close(self) -> None:
        self._flush_chunk()

    def count_cars(self) -> int:
        return 0


class CarSaver(ABC):
    @abstractmethod
    async def save_car(self, car: dict, car_id: str) -> None:
        raise NotImplementedError

    async def count_saved(self) -> int:
        return 0

    def close(self) -> None:
        pass


class SQLiteCarSaver(CarSaver):
    def __init__(self, storage: SQLiteStorage):
        self._s = storage

    @property
    def sqlite_path(self) -> str:
        return self._s.path

    async def save_car(self, car: dict, car_id: str) -> None:
        await asyncio.to_thread(self._s.save_car, car, car_id)

    async def count_saved(self) -> int:
        return await asyncio.to_thread(self._s.count_cars)

    def close(self) -> None:
        self._s.close()


class ChunkedJSONCarSaver(CarSaver):
    def __init__(self, storage: ChunkedJSONStorage):
        self._s = storage

    async def save_car(self, car: dict, car_id: str) -> None:
        await asyncio.to_thread(self._s.save_car, car, car_id)

    def close(self) -> None:
        self._s.close()


class PostgresCarSaver(CarSaver):
    """Один общий lock — кэши brand/model и одна транзакция за машину (psycopg2 не thread-safe)."""

    def __init__(self, dsn: str, store_raw: bool = False):
        import psycopg2  # lazy

        self._psycopg2 = psycopg2
        self.dsn = dsn
        self.store_raw = store_raw
        self._lock = asyncio.Lock()
        self._brand_cache: Dict[str, int] = {}
        self._model_cache: Dict[tuple, int] = {}
        self._migrate = _load_pg_migrate()

    def _save_sync(self, car: dict, car_id: str) -> None:
        m = self._migrate
        import psycopg2.extras

        payload = dict(car)
        raw_obj = car.get("_raw") if self.store_raw else None
        fields = m.row_to_car_fields(car_id, payload, sqlite_internal_id=None)
        with self._psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                bid = m.get_or_create_brand(cur, self._brand_cache, fields["mark"])
                mid = m.get_or_create_model(cur, self._model_cache, bid, fields["model"]) if bid else None
                raw_adapted = psycopg2.extras.Json(raw_obj) if raw_obj else None
                params = {
                    **fields,
                    "brand_id": bid,
                    "model_id": mid,
                    "data": psycopg2.extras.Json(payload),
                    "raw": raw_adapted,
                    "created_at": None,
                }
                cur.execute(m.UPSERT_CAR_SQL, params)
                row = cur.fetchone()
                if not row:
                    return
                car_pk = int(row[0])
                urls = m.extract_image_urls(payload)
                cur.execute("DELETE FROM car_images WHERE car_pk = %s", (car_pk,))
                for i, url in enumerate(urls):
                    cur.execute(
                        """
                        INSERT INTO car_images (car_pk, url, sort_order, is_primary)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (car_pk, url) DO UPDATE SET
                            sort_order = EXCLUDED.sort_order,
                            is_primary = EXCLUDED.is_primary
                        """,
                        (car_pk, url, i, i == 0),
                    )
            conn.commit()

    async def save_car(self, car: dict, car_id: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._save_sync, car, car_id)

    async def count_saved(self) -> int:
        async with self._lock:

            def _cnt() -> int:
                with self._psycopg2.connect(self.dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM cars")
                        r = cur.fetchone()
                        return int(r[0]) if r else 0

            return await asyncio.to_thread(_cnt)


def build_car_saver(
    config: dict,
) -> tuple[CarSaver, str]:
    """
    Возвращает (saver, backend_name).
    backend_name: sqlite | chunked_json | postgres
    """
    storage_cfg = config.get("storage", {})
    backend = storage_cfg.get("backend", "sqlite")
    store_raw = storage_cfg.get("store_raw_responses", False)
    if backend == "sqlite":
        path = storage_cfg.get("sqlite", {}).get("path", "encar_cars.db")
        s = SQLiteStorage(path, store_raw=store_raw)
        s.connect()
        return SQLiteCarSaver(s), "sqlite"
    if backend == "postgres":
        dsn = (storage_cfg.get("postgres") or {}).get("dsn") or ""
        dsn = str(dsn).strip()
        if not dsn:
            dsn = (os.environ.get("DATABASE_URL") or "").strip()
        if not dsn:
            raise ValueError("storage.backend=postgres requires storage.postgres.dsn or DATABASE_URL")
        return PostgresCarSaver(dsn, store_raw=store_raw), "postgres"
    cj = storage_cfg.get("chunked_json", {})
    s = ChunkedJSONStorage(
        cj.get("dir", "output_chunks"),
        cj.get("cars_per_file", 1000),
        store_raw=store_raw,
    )
    return ChunkedJSONCarSaver(s), "chunked_json"
