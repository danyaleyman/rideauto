"""
Пакетный upsert карточек в PostgreSQL (тот же SQL, что migrate_sqlite_to_postgres / PostgresCarSaver).
Используется скрейпером Dongchedi и может переиспользоваться другими ingestion-пайплайнами.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_pg_migrate():
    path = _REPO_ROOT / "infrastructure" / "postgresql" / "migrate_sqlite_to_postgres.py"
    spec = importlib.util.spec_from_file_location("wra_pg_migrate_catalog_upsert", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load migrate module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def upsert_json_batch(
    dsn: str,
    batch: List[Tuple[str, str]],
    *,
    batch_commit: int = 50,
) -> int:
    """
    batch: список (car_id, data_json) как в SQLite-скрейпере; raw не пишем (NULL).
    Возвращает число успешно обработанных записей.
    """
    if not batch:
        return 0
    import psycopg2
    import psycopg2.extras

    m = _load_pg_migrate()
    brand_cache: Dict[str, int] = {}
    model_cache: Dict[tuple, int] = {}
    ok = 0
    pending = 0
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            for car_id, data_json in batch:
                try:
                    payload = json.loads(data_json)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                fields = m.row_to_car_fields(car_id, payload, sqlite_internal_id=None)
                bid = m.get_or_create_brand(cur, brand_cache, fields["mark"])
                mid = m.get_or_create_model(cur, model_cache, bid, fields["model"]) if bid else None
                params = {
                    **fields,
                    "brand_id": bid,
                    "model_id": mid,
                    "data": psycopg2.extras.Json(payload),
                    "raw": None,
                    "created_at": None,
                }
                cur.execute(m.UPSERT_CAR_SQL, params)
                row = cur.fetchone()
                if not row:
                    continue
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
                ok += 1
                pending += 1
                if pending >= max(1, batch_commit):
                    conn.commit()
                    pending = 0
        if pending:
            conn.commit()
    finally:
        conn.close()
    return ok
