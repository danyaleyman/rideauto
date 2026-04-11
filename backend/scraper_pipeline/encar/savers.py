"""Saver: только PostgreSQL (каталог cars + car_images)."""

from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict
from catalog_pg_core import UPSERT_CAR_SQL, extract_image_urls, get_or_create_brand, get_or_create_model, row_to_car_fields

if TYPE_CHECKING:
    import psycopg2  # noqa: F401


def _repo_root() -> Path:
    # .../backend/scraper_pipeline/encar/savers.py → корень репозитория
    return Path(__file__).resolve().parents[2]


class CarSaver(ABC):
    @abstractmethod
    async def save_car(self, car: dict, car_id: str) -> None:
        raise NotImplementedError

    async def count_saved(self) -> int:
        return 0

    def close(self) -> None:
        pass


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

    def _save_sync(self, car: dict, car_id: str) -> None:
        import psycopg2.extras

        payload = dict(car)
        raw_obj = car.get("_raw") if self.store_raw else None
        fields = row_to_car_fields(car_id, payload, source_internal_id=None)
        # Postgres cars.source NOT NULL; API/Meilisearch ждут «encar» для Кореи (см. fastapi_app).
        if not fields.get("source"):
            fields["source"] = "encar"
        with self._psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                bid = get_or_create_brand(cur, self._brand_cache, fields["mark"])
                mid = get_or_create_model(cur, self._model_cache, bid, fields["model"]) if bid else None
                raw_adapted = psycopg2.extras.Json(raw_obj) if raw_obj else None
                params = {
                    **fields,
                    "brand_id": bid,
                    "model_id": mid,
                    "data": psycopg2.extras.Json(payload),
                    "raw": raw_adapted,
                    "created_at": None,
                }
                cur.execute(UPSERT_CAR_SQL, params)
                row = cur.fetchone()
                if not row:
                    return
                car_pk = int(row[0])
                urls = extract_image_urls(payload)
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


def build_car_saver(config: dict) -> tuple[CarSaver, str]:
    storage_cfg = config.get("storage", {})
    backend = storage_cfg.get("backend", "postgres")
    if backend != "postgres":
        raise ValueError(
            f"Поддерживается только storage.backend=postgres (дано {backend!r}). "
            "Задайте DATABASE_URL или storage.postgres.dsn."
        )
    store_raw = storage_cfg.get("store_raw_responses", False)
    dsn = (storage_cfg.get("postgres") or {}).get("dsn") or ""
    dsn = str(dsn).strip()
    if not dsn:
        dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise ValueError("storage.backend=postgres requires storage.postgres.dsn or DATABASE_URL")
    return PostgresCarSaver(dsn, store_raw=store_raw), "postgres"
