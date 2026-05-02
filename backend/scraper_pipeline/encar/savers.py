"""Saver: только PostgreSQL (каталог cars + car_images)."""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import os
from datetime import datetime, timedelta, timezone
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict
from catalog_pg_core import UPSERT_CAR_SQL, extract_image_urls, get_or_create_brand, get_or_create_model, row_to_car_fields
from scraper_pipeline.pg_dsn_resolve import resolve_scraper_postgres_dsn

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
        self._save_count = 0
        self._snapshot_enabled = str(os.environ.get("RAW_SNAPSHOT_ENABLED", "1")).strip().lower() in {"1", "true", "yes"}
        self._snapshot_dir = Path(
            (os.environ.get("RAW_SNAPSHOT_DIR") or str(_repo_root() / "backend" / "data" / "raw_snapshots")).strip()
        )
        self._snapshot_retention_days = int(os.environ.get("RAW_SNAPSHOT_RETENTION_DAYS", "14") or 14)

    @staticmethod
    def _redact_raw(obj: Any) -> Any:
        pii_keys = {
            "phone",
            "mobile",
            "tel",
            "email",
            "contact",
            "addressDetail",
            "residentNo",
            "ssn",
        }
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                key = str(k)
                if key.lower() in {x.lower() for x in pii_keys}:
                    out[key] = "***redacted***"
                else:
                    out[key] = PostgresCarSaver._redact_raw(v)
            return out
        if isinstance(obj, list):
            return [PostgresCarSaver._redact_raw(x) for x in obj]
        return obj

    @staticmethod
    def _encode_raw(raw_obj: Any) -> Dict[str, Any]:
        payload = json.dumps(raw_obj, ensure_ascii=False).encode("utf-8")
        gz = gzip.compress(payload, compresslevel=5)
        return {
            "encoding": "gzip+base64+json",
            "blob": base64.b64encode(gz).decode("ascii"),
            "raw_size": len(payload),
            "compressed_size": len(gz),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

    def _write_snapshot(self, car_id: str, raw_obj: Any) -> None:
        if not self._snapshot_enabled:
            return
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self._snapshot_dir / f"encar_raw_{day}.jsonl"
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "car_id": str(car_id),
            "raw": raw_obj,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _cleanup_snapshots(self) -> None:
        if not self._snapshot_enabled or self._snapshot_retention_days <= 0:
            return
        if not self._snapshot_dir.is_dir():
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._snapshot_retention_days)
        for p in self._snapshot_dir.glob("encar_raw_*.jsonl"):
            try:
                if datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) < cutoff:
                    p.unlink(missing_ok=True)
            except Exception:
                continue

    def _save_sync(self, car: dict, car_id: str) -> None:
        import psycopg2.extras

        payload = dict(car)
        raw_obj = car.get("_raw") if self.store_raw else None
        raw_obj = self._redact_raw(raw_obj) if raw_obj is not None else None
        encoded_raw = self._encode_raw(raw_obj) if raw_obj is not None else None
        fields = row_to_car_fields(car_id, payload, source_internal_id=None)
        # Postgres cars.source NOT NULL; API/Meilisearch ждут «encar» для Кореи (см. fastapi_app).
        if not fields.get("source"):
            fields["source"] = "encar"
        with self._psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                bid = get_or_create_brand(cur, self._brand_cache, fields["mark"])
                mid = get_or_create_model(cur, self._model_cache, bid, fields["model"]) if bid else None
                raw_adapted = psycopg2.extras.Json(encoded_raw) if encoded_raw else None
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
        if raw_obj is not None:
            self._write_snapshot(car_id, raw_obj)
        self._save_count += 1
        if self._save_count % 250 == 0:
            self._cleanup_snapshots()

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
    dsn = str(resolve_scraper_postgres_dsn(config) or "").strip()
    if not dsn:
        raise ValueError("storage.backend=postgres requires storage.postgres.dsn or DATABASE_URL or RIDEAUTO_PG_CHECKPOINT_DSN")
    return PostgresCarSaver(dsn, store_raw=store_raw), "postgres"
