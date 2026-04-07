#!/usr/bin/env python3
"""
Load SQLite catalog DBs (encar_cars.db, encar_china.db) into PostgreSQL using
`infrastructure/postgresql/schema.sql`.

Derivations mirror backend/api_server.py::_build_filter_sql where applicable.

Usage:
  python migrate_sqlite_to_postgres.py --dsn "postgresql://user:pass@localhost:5432/wra" \\
      --sqlite encar_cars.db [--sqlite encar_china.db]

Requirements:
  pip install psycopg2-binary

Order of --sqlite matters for upserts: later files overwrite same car_id (if any overlap).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Install psycopg2-binary: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def _d(obj: Dict[str, Any]) -> Dict[str, Any]:
    out = obj.get("data")
    return out if isinstance(out, dict) else {}


def _optional_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _drive_type(d: Dict[str, Any]) -> Optional[str]:
    v = d.get("drive_type") or d.get("prep_drive_type")
    return _optional_str(v)


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def year_from_data(d: Dict[str, Any]) -> Optional[int]:
    y_raw = d.get("year")
    if y_raw is None:
        return None
    s = str(y_raw).strip()
    if len(s) < 4:
        return None
    try:
        return int(s[:4])
    except ValueError:
        return None


def year_month_ordinal(d: Dict[str, Any]) -> Optional[int]:
    ym = (d.get("yearMonth") or "").strip() if isinstance(d.get("yearMonth"), str) else ""
    if isinstance(d.get("yearMonth"), (int, float)):
        ym = str(int(d.get("yearMonth")))
    y_raw = d.get("year") or ""
    if ym and len(ym) >= 6:
        try:
            y = int(ym[0:4])
            m = int(ym[4:6]) - 1
            return y * 12 + m
        except ValueError:
            return None
    s = str(y_raw).strip()
    if len(s) >= 4:
        try:
            y = int(s[:4])
            return y * 12 + 0
        except ValueError:
            return None
    return None


def listing_partition_key(car_id: str, d: Dict[str, Any]) -> str:
    inner = (d.get("inner_id") or "").strip()
    if inner:
        return inner
    did = (d.get("id") or "").strip()
    if did:
        return did
    return (car_id or "").strip()


def normalized_source(d: Dict[str, Any]) -> str:
    raw = (d.get("source") or "").strip().lower()
    if raw == "dongchedi":
        return "dongchedi"
    if raw:
        return raw
    return "encar"


def insurance_cases_and_payout_krw(payload: Dict[str, Any]) -> Tuple[int, float]:
    d = _d(payload)
    extra = d.get("extra") if isinstance(d.get("extra"), dict) else {}
    ro = extra.get("record_open") if isinstance(extra.get("record_open"), dict) else {}
    acc = ro.get("accidents")
    if acc is None:
        return 0, 0.0
    if isinstance(acc, str):
        try:
            acc = json.loads(acc)
        except json.JSONDecodeError:
            return 0, 0.0
    if not isinstance(acc, list):
        return 0, 0.0
    total = 0.0
    for item in acc:
        if not isinstance(item, dict):
            continue
        v = item.get("insuranceBenefit")
        f = _safe_float(v)
        if f is not None:
            total += f
    return len(acc), total


def insurance_payout_rub(d: Dict[str, Any], payout_krw: float) -> float:
    usdt_rub = _safe_float(d.get("usdt_rub")) or 91.0
    krw_per_usdt = _safe_float(d.get("krw_per_usdt")) or 1400.0
    if krw_per_usdt == 0:
        return 0.0
    return payout_krw * (usdt_rub / krw_per_usdt)


def damaged_parts_count(payload: Dict[str, Any]) -> int:
    d = _d(payload)
    extra = d.get("extra") if isinstance(d.get("extra"), dict) else {}
    ins = extra.get("inspection_structured") if isinstance(extra.get("inspection_structured"), dict) else {}
    bc = ins.get("bodyChanged")
    if bc is None:
        return 0
    if isinstance(bc, dict):
        return len(bc)
    if isinstance(bc, list):
        return len(bc)
    if isinstance(bc, str):
        try:
            obj = json.loads(bc)
            if isinstance(obj, dict):
                return len(obj)
            if isinstance(obj, list):
                return len(obj)
        except json.JSONDecodeError:
            return 0
    return 0


def power_hp(payload: Dict[str, Any]) -> Optional[int]:
    d = _d(payload)
    for k in ("power", "hp"):
        v = _safe_int(d.get(k))
        if v is not None:
            return v
    v = _safe_int(payload.get("power"))
    return v


def offer_created_at(payload: Dict[str, Any]) -> Optional[datetime]:
    d = _d(payload)
    raw = d.get("offer_created") or d.get("created_at")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def sqlite_ts_to_timestamptz(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def extract_image_urls(payload: Dict[str, Any]) -> List[str]:
    d = _d(payload)
    raw = d.get("images")
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        if isinstance(x, str):
            u = x.strip()
            if u:
                out.append(u)
    return out


def get_or_create_brand(cur: Any, cache: Dict[str, int], name: Optional[str]) -> Optional[int]:
    name = (name or "").strip()
    if not name:
        return None
    key = name.lower()
    if key in cache:
        return cache[key]
    cur.execute(
        "INSERT INTO brands (name) VALUES (%s) ON CONFLICT (name_norm) DO NOTHING RETURNING id",
        (name,),
    )
    row = cur.fetchone()
    if row:
        bid = int(row[0])
    else:
        cur.execute("SELECT id FROM brands WHERE name_norm = lower(trim(%s))", (name,))
        r2 = cur.fetchone()
        bid = int(r2[0]) if r2 else None
    if bid is None:
        raise RuntimeError(f"brand upsert failed for {name!r}")
    cache[key] = bid
    return bid


def get_or_create_model(cur: Any, cache: Dict[Tuple[int, str], int], brand_id: int, name: Optional[str]) -> Optional[int]:
    name = (name or "").strip()
    if not name:
        return None
    key = (brand_id, name.lower())
    if key in cache:
        return cache[key]
    cur.execute(
        """
        INSERT INTO models (brand_id, name) VALUES (%s, %s)
        ON CONFLICT (brand_id, name_norm) DO NOTHING RETURNING id
        """,
        (brand_id, name),
    )
    row = cur.fetchone()
    if row:
        mid = int(row[0])
    else:
        cur.execute(
            "SELECT id FROM models WHERE brand_id = %s AND name_norm = lower(trim(%s))",
            (brand_id, name),
        )
        r2 = cur.fetchone()
        mid = int(r2[0]) if r2 else None
    if mid is None:
        raise RuntimeError(f"model upsert failed for brand_id={brand_id} name={name!r}")
    cache[key] = mid
    return mid


def iter_sqlite_rows(path: Path) -> Iterator[Tuple[int, str, str, Optional[str], Optional[str]]]:
    conn = sqlite3.connect(str(path), timeout=120.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT id, car_id, data_json, raw_json, created_at FROM cars ORDER BY id ASC"
        )
        while True:
            rows = cur.fetchmany(500)
            if not rows:
                break
            for r in rows:
                yield (
                    int(r["id"]),
                    str(r["car_id"]),
                    str(r["data_json"]),
                    r["raw_json"] if r["raw_json"] is not None else None,
                    r["created_at"] if r["created_at"] is not None else None,
                )
    finally:
        conn.close()


def row_to_car_fields(
    car_id: str,
    payload: Dict[str, Any],
    *,
    sqlite_internal_id: Optional[int] = None,
) -> Dict[str, Any]:
    d = _d(payload)
    mark = (d.get("mark") or "").strip() or None
    model = (d.get("model") or "").strip() or None
    generation = _optional_str(d.get("generation") or d.get("configuration"))
    trim_name = _optional_str(d.get("gradeName") or d.get("configuration") or d.get("generation"))
    ins_n, ins_krw = insurance_cases_and_payout_krw(payload)
    return {
        "car_id": car_id,
        "mark": mark,
        "model": model,
        "generation": generation,
        "trim_name": trim_name,
        "body_type": _optional_str(d.get("body_type")),
        "fuel_type": _optional_str(d.get("engine_type")),
        "transmission_type": _optional_str(d.get("transmission_type")),
        "drive_type": _drive_type(d),
        "color": _optional_str(d.get("color")),
        "source": normalized_source(d),
        "listing_partition_key": listing_partition_key(car_id, d),
        "power_hp": power_hp(payload),
        "displacement_cc": _safe_int(d.get("displacement")),
        "price_rub": _safe_float(d.get("my_price")),
        "mileage_km": _safe_int(d.get("km_age")),
        "year": year_from_data(d),
        "year_month": year_month_ordinal(d),
        "insurance_cases": ins_n,
        "insurance_payout_krw": ins_krw,
        "insurance_payout_rub": insurance_payout_rub(d, ins_krw),
        "damaged_parts_count": damaged_parts_count(payload),
        "offer_created_at": offer_created_at(payload),
        "sqlite_internal_id": sqlite_internal_id,
    }


UPSERT_CAR_SQL = """
INSERT INTO cars (
    car_id, brand_id, model_id, mark, model, generation, trim_name,
    body_type, fuel_type, transmission_type, drive_type, color,
    source, listing_partition_key,
    power_hp, displacement_cc, price_rub, mileage_km, year, year_month,
    insurance_cases, insurance_payout_krw, insurance_payout_rub, damaged_parts_count,
    offer_created_at, data, raw, sqlite_internal_id, created_at, updated_at
) VALUES (
    %(car_id)s, %(brand_id)s, %(model_id)s, %(mark)s, %(model)s, %(generation)s, %(trim_name)s,
    %(body_type)s, %(fuel_type)s, %(transmission_type)s, %(drive_type)s, %(color)s,
    %(source)s, %(listing_partition_key)s,
    %(power_hp)s, %(displacement_cc)s, %(price_rub)s, %(mileage_km)s, %(year)s, %(year_month)s,
    %(insurance_cases)s, %(insurance_payout_krw)s, %(insurance_payout_rub)s, %(damaged_parts_count)s,
    %(offer_created_at)s, %(data)s, %(raw)s,
    %(sqlite_internal_id)s, COALESCE(%(created_at)s, now()), now()
)
ON CONFLICT (car_id) DO UPDATE SET
    brand_id = EXCLUDED.brand_id,
    model_id = EXCLUDED.model_id,
    mark = EXCLUDED.mark,
    model = EXCLUDED.model,
    generation = EXCLUDED.generation,
    trim_name = EXCLUDED.trim_name,
    body_type = EXCLUDED.body_type,
    fuel_type = EXCLUDED.fuel_type,
    transmission_type = EXCLUDED.transmission_type,
    drive_type = EXCLUDED.drive_type,
    color = EXCLUDED.color,
    source = EXCLUDED.source,
    listing_partition_key = EXCLUDED.listing_partition_key,
    power_hp = EXCLUDED.power_hp,
    displacement_cc = EXCLUDED.displacement_cc,
    price_rub = EXCLUDED.price_rub,
    mileage_km = EXCLUDED.mileage_km,
    year = EXCLUDED.year,
    year_month = EXCLUDED.year_month,
    insurance_cases = EXCLUDED.insurance_cases,
    insurance_payout_krw = EXCLUDED.insurance_payout_krw,
    insurance_payout_rub = EXCLUDED.insurance_payout_rub,
    damaged_parts_count = EXCLUDED.damaged_parts_count,
    offer_created_at = EXCLUDED.offer_created_at,
    data = EXCLUDED.data,
    raw = EXCLUDED.raw,
    sqlite_internal_id = EXCLUDED.sqlite_internal_id,
    updated_at = now()
RETURNING id
"""


def apply_schema(conn: Any, schema_path: Path) -> None:
    """Apply multi-statement schema (psycopg2 executes one statement per call)."""
    text = schema_path.read_text(encoding="utf-8")

    def split_sql_statements(script_text: str) -> List[str]:
        """Split SQL script by semicolon, skipping strings/comments."""
        stmts: List[str] = []
        cur: List[str] = []
        i = 0
        n = len(script_text)
        in_single = False
        in_double = False
        in_line_comment = False
        in_block_comment = False
        in_dollar: Optional[str] = None
        while i < n:
            ch = script_text[i]
            nxt = script_text[i + 1] if i + 1 < n else ""
            if in_line_comment:
                cur.append(ch)
                if ch == "\n":
                    in_line_comment = False
                i += 1
                continue
            if in_block_comment:
                cur.append(ch)
                if ch == "*" and nxt == "/":
                    cur.append(nxt)
                    i += 2
                    in_block_comment = False
                    continue
                i += 1
                continue
            if in_dollar is not None:
                cur.append(ch)
                if script_text.startswith(in_dollar, i):
                    for j in range(1, len(in_dollar)):
                        cur.append(script_text[i + j])
                    i += len(in_dollar)
                    in_dollar = None
                    continue
                i += 1
                continue
            if in_single:
                cur.append(ch)
                if ch == "'" and nxt == "'":
                    cur.append(nxt)
                    i += 2
                    continue
                if ch == "'":
                    in_single = False
                i += 1
                continue
            if in_double:
                cur.append(ch)
                if ch == '"':
                    in_double = False
                i += 1
                continue
            if ch == "-" and nxt == "-":
                cur.append(ch)
                cur.append(nxt)
                i += 2
                in_line_comment = True
                continue
            if ch == "/" and nxt == "*":
                cur.append(ch)
                cur.append(nxt)
                i += 2
                in_block_comment = True
                continue
            if ch == "$":
                j = i + 1
                while j < n and (script_text[j].isalnum() or script_text[j] == "_"):
                    j += 1
                if j < n and script_text[j] == "$":
                    tag = script_text[i : j + 1]
                    cur.append(tag)
                    i = j + 1
                    in_dollar = tag
                    continue
            if ch == "'":
                cur.append(ch)
                in_single = True
                i += 1
                continue
            if ch == '"':
                cur.append(ch)
                in_double = True
                i += 1
                continue
            if ch == ";":
                stmt = "".join(cur).strip()
                if stmt:
                    stmts.append(stmt)
                cur = []
                i += 1
                continue
            cur.append(ch)
            i += 1
        tail = "".join(cur).strip()
        if tail:
            stmts.append(tail)
        return stmts

    buf: List[str] = []
    with conn.cursor() as cur:
        for line in text.splitlines():
            t = line.strip()
            if t.upper() in ("BEGIN;", "BEGIN"):
                continue
            if t.upper() in ("COMMIT;", "COMMIT"):
                continue
            buf.append(line)
        script = "\n".join(buf)
        parts = split_sql_statements(script)
        for part in parts:
            first_noncomment = "\n".join(
                ln for ln in part.splitlines() if ln.strip() and not ln.strip().startswith("--")
            )
            if not first_noncomment.strip():
                continue
            cur.execute(part + ";")
    conn.commit()


def migrate_file(
    pg: Any,
    sqlite_path: Path,
    batch_commit: int,
) -> Tuple[int, int]:
    brand_cache: Dict[str, int] = {}
    model_cache: Dict[Tuple[int, str], int] = {}
    n_cars = 0
    n_images = 0
    with pg.cursor() as cur:
        pending = 0
        for sqlite_id, car_id, data_json, raw_json, created_sqlite in iter_sqlite_rows(sqlite_path):
            try:
                payload = json.loads(data_json)
            except json.JSONDecodeError:
                continue
            fields = row_to_car_fields(car_id, payload, sqlite_internal_id=sqlite_id)
            bid = get_or_create_brand(cur, brand_cache, fields["mark"])
            mid = get_or_create_model(cur, model_cache, bid, fields["model"]) if bid else None
            raw_adapted: Any
            if raw_json:
                try:
                    raw_adapted = psycopg2.extras.Json(json.loads(raw_json))
                except json.JSONDecodeError:
                    raw_adapted = psycopg2.extras.Json({"_raw_text": raw_json})
            else:
                raw_adapted = None
            params = {
                **fields,
                "brand_id": bid,
                "model_id": mid,
                "data": psycopg2.extras.Json(payload),
                "raw": raw_adapted,
                "created_at": sqlite_ts_to_timestamptz(created_sqlite),
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
            n_images += len(urls)
            n_cars += 1
            pending += 1
            if pending >= batch_commit:
                pg.commit()
                pending = 0
        if pending:
            pg.commit()
    return n_cars, n_images


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="SQLite cars → PostgreSQL")
    parser.add_argument(
        "--dsn",
        default="",
        help='PostgreSQL DSN, e.g. postgresql://wra:wra@localhost:5432/wra',
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=root / "schema.sql",
        help="Path to schema.sql",
    )
    parser.add_argument(
        "--sqlite",
        action="append",
        dest="sqlite_paths",
        default=[],
        help="SQLite file (repeat for encar_cars.db then encar_china.db)",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Do not execute schema.sql (schema already applied)",
    )
    parser.add_argument(
        "--batch-commit",
        type=int,
        default=200,
        help="Commit every N cars",
    )
    args = parser.parse_args()
    if not args.dsn:
        parser.error("--dsn is required")
    paths = [Path(p).expanduser().resolve() for p in (args.sqlite_paths or [])]
    if not paths:
        parser.error("pass at least one --sqlite path")
    for p in paths:
        if not p.is_file():
            parser.error(f"SQLite file not found: {p}")

    pg = psycopg2.connect(args.dsn)
    try:
        pg.autocommit = False
        if not args.skip_schema:
            apply_schema(pg, args.schema)
        total_cars = 0
        total_images = 0
        for sp in paths:
            c, im = migrate_file(pg, sp, max(1, args.batch_commit))
            print(f"{sp.name}: cars_upserted={c} image_rows={im}", flush=True)
            total_cars += c
            total_images += im
        print(f"done: cars_upserted={total_cars} image_rows_written={total_images}", flush=True)
    finally:
        pg.close()


if __name__ == "__main__":
    main()
