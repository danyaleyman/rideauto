from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import asyncpg


async def fetch_cars_by_ids(pool: asyncpg.Pool, car_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Возвращает полные JSON-карточки из колонки `cars.data`."""
    if not car_ids:
        return {}
    rows = await pool.fetch(
        "SELECT car_id, data, created_at FROM cars WHERE car_id = ANY($1::text[])",
        car_ids,
    )
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        cid = str(r["car_id"])
        data = r["data"]
        if isinstance(data, (bytes, memoryview)):
            data = bytes(data).decode("utf-8")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                continue
        if not isinstance(data, dict):
            continue
        obj = dict(data)
        obj["id"] = cid
        ca = r.get("created_at")
        if ca is not None:
            try:
                obj["_catalog_created_at"] = ca.isoformat() if hasattr(ca, "isoformat") else str(ca)
            except Exception:
                pass
        out[cid] = obj
    return out


async def fetch_car_any_id(pool: asyncpg.Pool, ref: str) -> Optional[Dict[str, Any]]:
    """Поиск по car_id или inner_id в JSON (как _car_row_by_any_id)."""
    if not ref or not ref.strip():
        return None
    q = ref.strip()
    row = await pool.fetchrow(
        """
        SELECT car_id, data
        FROM cars
        WHERE car_id = $1
           OR (data->>'id') = $1
           OR (data->'data'->>'inner_id') = $1
           OR (data->>'inner_id') = $1
        ORDER BY id DESC
        LIMIT 1
        """,
        q,
    )
    if not row:
        return None
    cid = str(row["car_id"])
    data = row["data"]
    if isinstance(data, (bytes, memoryview)):
        data = bytes(data).decode("utf-8")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    obj = dict(data)
    obj["id"] = cid
    return obj
