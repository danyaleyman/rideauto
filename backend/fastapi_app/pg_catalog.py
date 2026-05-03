from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from catalog_dedupe import terminal_car_id_for_dedupe_map


def _merge_catalog_timestamps(obj: Dict[str, Any], row: Any) -> None:
    ca = row.get("created_at")
    if ca is not None:
        try:
            obj["_catalog_created_at"] = ca.isoformat() if hasattr(ca, "isoformat") else str(ca)
        except Exception:
            pass
    ua = row.get("updated_at")
    if ua is not None:
        try:
            obj["_catalog_updated_at"] = ua.isoformat() if hasattr(ua, "isoformat") else str(ua)
        except Exception:
            pass


def _row_to_car_obj(row: asyncpg.Record) -> Optional[Dict[str, Any]]:
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


def _apply_row_flags(obj: Dict[str, Any], row: asyncpg.Record) -> None:
    _merge_catalog_timestamps(obj, row)
    if row["encar_listing_sold"] is True:
        obj["encar_listing_sold"] = True
    if row["dongchedi_listing_sold"] is True:
        obj["dongchedi_listing_sold"] = True


_SELECT_CAR_ROWS = """
    SELECT car_id, data, created_at, updated_at, encar_listing_sold, dongchedi_listing_sold,
           dedupe_canonical_car_id
    FROM cars
    WHERE car_id = ANY($1::text[])
"""


async def _load_cars_closure(pool: asyncpg.Pool, seeds: List[str]) -> Tuple[Dict[str, asyncpg.Record], Dict[str, Optional[str]]]:
    """Загружает строки cars, следуя dedupe_canonical_car_id, пока не соберутся все узлы цепочки."""
    by_cid: Dict[str, asyncpg.Record] = {}
    pending = {str(x).strip() for x in seeds if str(x).strip()}
    for _ in range(12):
        if not pending:
            break
        chunk = [x for x in pending if x not in by_cid]
        if not chunk:
            break
        rows = await pool.fetch(_SELECT_CAR_ROWS, chunk)
        pending = set()
        for r in rows:
            cid = str(r["car_id"])
            by_cid[cid] = r
            dcc = r.get("dedupe_canonical_car_id")
            if dcc:
                t = str(dcc).strip()
                if t and t not in by_cid:
                    pending.add(t)
    dedupe_map: Dict[str, Optional[str]] = {}
    for cid, r in by_cid.items():
        dcc = r.get("dedupe_canonical_car_id")
        dedupe_map[cid] = str(dcc).strip() if dcc is not None and str(dcc).strip() else None
    return by_cid, dedupe_map


async def fetch_cars_by_ids(pool: asyncpg.Pool, car_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Возвращает полные JSON-карточки из колонки `cars.data`; дубли разрешаются на каноническую строку."""
    if not car_ids:
        return {}
    uniq = list(dict.fromkeys(str(x).strip() for x in car_ids if str(x).strip()))
    by_cid, dedupe_map = await _load_cars_closure(pool, uniq)

    out: Dict[str, Dict[str, Any]] = {}
    for req in uniq:
        term = terminal_car_id_for_dedupe_map(dedupe_map, req)
        row = by_cid.get(term)
        if row is None:
            continue
        obj = _row_to_car_obj(row)
        if obj is None:
            continue
        _apply_row_flags(obj, row)
        out[req] = obj
    return out


async def fetch_car_any_id(pool: asyncpg.Pool, ref: str) -> Optional[Dict[str, Any]]:
    """Поиск по car_id или inner_id в JSON (как _car_row_by_any_id); дубли → каноническая карточка."""
    if not ref or not ref.strip():
        return None
    q = ref.strip()
    row = await pool.fetchrow(
        """
        SELECT car_id, data, created_at, updated_at, encar_listing_sold, dongchedi_listing_sold,
               dedupe_canonical_car_id
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

    seen: set[str] = set()
    for _ in range(12):
        dcc = row.get("dedupe_canonical_car_id")
        if not dcc or not str(dcc).strip():
            break
        nxt = str(dcc).strip()
        if nxt in seen:
            break
        seen.add(nxt)
        nxt_row = await pool.fetchrow(
            """
            SELECT car_id, data, created_at, updated_at, encar_listing_sold, dongchedi_listing_sold,
                   dedupe_canonical_car_id
            FROM cars
            WHERE car_id = $1
            LIMIT 1
            """,
            nxt,
        )
        if not nxt_row:
            break
        row = nxt_row

    obj = _row_to_car_obj(row)
    if obj is None:
        return None
    _apply_row_flags(obj, row)
    return obj
