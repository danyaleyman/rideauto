"""
Пакетный upsert карточек в PostgreSQL (общая SQL-логика с PostgresCarSaver).
Используется скрейпером Dongchedi и может переиспользоваться другими ingestion-пайплайнами.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from catalog_pg_core import UPSERT_CAR_SQL, extract_image_urls, get_or_create_brand, get_or_create_model, row_to_car_fields


def upsert_json_batch(
    dsn: str,
    batch: List[Tuple[str, str]],
    *,
    batch_commit: int = 50,
) -> int:
    """
    batch: список (car_id, data_json); raw не пишем (NULL).
    Возвращает число успешно обработанных записей.
    """
    if not batch:
        return 0
    import psycopg2
    import psycopg2.extras

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
                payload["_catalog_needs_pricing_recompute"] = True
                fields = row_to_car_fields(car_id, payload, source_internal_id=None)
                payload.pop("_catalog_needs_pricing_recompute", None)
                bid = get_or_create_brand(cur, brand_cache, fields["mark"])
                mid = get_or_create_model(cur, model_cache, bid, fields["model"]) if bid else None
                params = {
                    **fields,
                    "brand_id": bid,
                    "model_id": mid,
                    "data": psycopg2.extras.Json(payload),
                    "raw": None,
                    "created_at": None,
                    "sync_clear_pricing_recompute_queue": False,
                }
                cur.execute(UPSERT_CAR_SQL, params)
                row = cur.fetchone()
                if not row:
                    continue
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
