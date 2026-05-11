from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from catalog_dedupe import terminal_car_id_for_dedupe_map
from catalog_pg_core import normalize_calendar_year_value

_log = logging.getLogger(__name__)

# Источники, выведенные из каталога: при отсутствии строки по car_id не ходим в JSON-fallback (seq scan / таймаут).
DEPRECATED_SOURCES: Tuple[str, ...] = ("dongchedi",)


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


def _scalar_year_missing(v: Any) -> bool:
    return v is None or v == "" or v == 0


def _merge_denormalized_year_from_row(obj: Dict[str, Any], row: asyncpg.Record) -> None:
    """Подмешивает cars.year / cars.year_month, если в JSON их нет (чипы и slim.year_num)."""
    row_y = row.get("year")
    row_ym = row.get("year_month")
    if row_y is None and row_ym is None:
        return
    inner = obj.get("data")
    target: Dict[str, Any] = inner if isinstance(inner, dict) else obj
    if row_y is not None and _scalar_year_missing(target.get("year")):
        try:
            iy = int(row_y)
        except (TypeError, ValueError):
            iy = None
        cy = normalize_calendar_year_value(iy) if iy is not None else None
        if cy is not None:
            target["year"] = cy
    if row_ym is not None and _scalar_year_missing(target.get("yearMonth")) and _scalar_year_missing(
        target.get("year_month")
    ):
        try:
            iym = int(row_ym)
        except (TypeError, ValueError):
            iym = None
        if iym is not None and 190_001 <= iym <= 210_012:
            mo = iym % 100
            if 1 <= mo <= 12:
                target["yearMonth"] = str(iym)


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
    _merge_denormalized_year_from_row(obj, row)
    return obj


def _apply_row_flags(obj: Dict[str, Any], row: asyncpg.Record) -> None:
    _merge_catalog_timestamps(obj, row)
    if row["encar_listing_sold"] is True:
        obj["encar_listing_sold"] = True
    if row["che168_listing_sold"] is True:
        obj["che168_listing_sold"] = True


_SELECT_CAR_ROWS = """
    SELECT car_id, data, created_at, updated_at, encar_listing_sold, che168_listing_sold,
           dedupe_canonical_car_id, year, year_month
    FROM cars
    WHERE car_id = ANY($1::text[])
"""

_SELECT_CAR_COLS = """
    car_id, data, created_at, updated_at, encar_listing_sold, che168_listing_sold,
    dedupe_canonical_car_id, year, year_month
"""

# Несколько вариантов car_id за один проход по уникальному индексу (голый inner_id в URL vs encar-… в БД).
_SELECT_CAR_BY_ANY_CAR_ID = f"""
    SELECT {_SELECT_CAR_COLS.strip()}
    FROM cars
    WHERE car_id = ANY($1::text[])
    ORDER BY id DESC
    LIMIT 1
"""

# По одному предикату на запрос — планировщик может использовать btree-индексы на выражениях
# (миграция idx_cars_data_json_*). OR в одном запросе на большой таблице даёт seq scan до таймаута.
_SELECT_CAR_BY_DATA_ID = f"""
    SELECT {_SELECT_CAR_COLS.strip()}
    FROM cars
    WHERE (data->>'id') = $1
    ORDER BY id DESC
    LIMIT 1
"""
_SELECT_CAR_BY_INNER_ID = f"""
    SELECT {_SELECT_CAR_COLS.strip()}
    FROM cars
    WHERE (data->>'inner_id') = $1
    ORDER BY id DESC
    LIMIT 1
"""
_SELECT_CAR_BY_NESTED_INNER_ID = f"""
    SELECT {_SELECT_CAR_COLS.strip()}
    FROM cars
    WHERE (data->'data'->>'inner_id') = $1
    ORDER BY id DESC
    LIMIT 1
"""


def _car_id_lookup_candidates(ref: str) -> List[str]:
    q = (ref or "").strip()
    if not q:
        return []
    out: List[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(q)
    # Поиск/карточка часто отдают голый числовой id (Encar), в БД — encar-41730887 и т.п.
    if q.isdigit():
        for prefix in ("encar", "che168", "dongchedi"):
            add(f"{prefix}-{q}")
    return out


async def _fetch_row_by_json_ref_fields(pool: asyncpg.Pool, ref: str) -> Optional[asyncpg.Record]:
    for sql in (_SELECT_CAR_BY_DATA_ID, _SELECT_CAR_BY_INNER_ID, _SELECT_CAR_BY_NESTED_INNER_ID):
        row = await pool.fetchrow(sql, ref)
        if row is not None:
            return row
    return None


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


def _is_deprecated_prefixed_ref(q: str) -> bool:
    ql = q.lower()
    return any(ql.startswith(f"{src}-") for src in DEPRECATED_SOURCES)


async def fetch_car_any_id(pool: asyncpg.Pool, ref: str) -> Optional[Dict[str, Any]]:
    """Поиск по car_id или inner_id в JSON (как _car_row_by_any_id); дубли → каноническая карточка."""
    if not ref or not ref.strip():
        return None
    q = ref.strip()
    row = await pool.fetchrow(_SELECT_CAR_BY_ANY_CAR_ID, _car_id_lookup_candidates(q))
    if not row:
        # Мёртвые ссылки deprecated-* без car_id: JSON-fallback сканирует таблицу до command_timeout.
        if _is_deprecated_prefixed_ref(q):
            _log.debug("fetch_car_any_id: skip JSON fallback for deprecated source ref=%r", q)
            return None
        row = await _fetch_row_by_json_ref_fields(pool, q)
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
            SELECT car_id, data, created_at, updated_at, encar_listing_sold, che168_listing_sold,
                   dedupe_canonical_car_id, year, year_month
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
