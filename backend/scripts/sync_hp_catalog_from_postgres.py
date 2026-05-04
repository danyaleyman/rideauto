#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, Tuple

import psycopg2
import psycopg2.extras

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from engine_hp_resolver import extract_motor_code
from hp_catalog_store import (
    DEFAULT_DB_PATH,
    connect,
    ensure_schema,
    hp_to_kw,
    normalize_key_part,
    normalize_text,
    parse_displacement_cc,
    parse_hp,
    parse_year_month,
)


def _dsn(args_dsn: str) -> str:
    return (args_dsn or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN") or "").strip()


def _motor_vin_from_pg_data(raw: Any) -> Tuple[str, str]:
    blob: Any = raw
    if blob is None:
        return "", ""
    if isinstance(blob, (bytes, memoryview)):
        try:
            blob = json.loads(bytes(blob).decode("utf-8", errors="replace"))
        except Exception:
            blob = {}
    elif isinstance(blob, str):
        try:
            blob = json.loads(blob)
        except json.JSONDecodeError:
            blob = {}

    candidates: list[dict] = []
    if isinstance(blob, dict):
        candidates.append(blob)
        inner = blob.get("data")
        if isinstance(inner, dict):
            candidates.append(inner)

    motor_raw = ""
    for c in candidates:
        m = extract_motor_code(c)
        if m:
            motor_raw = m
            break
    motor_n = normalize_key_part(motor_raw) if motor_raw else ""

    vin = ""
    for c in candidates:
        v = str(c.get("vin") or "").strip().upper()
        if v:
            vin = v
            break
    return motor_n, (vin[:11] if vin else "")


def _row_values(row: dict) -> Tuple[str, str, str, str, Optional[int], str, Optional[int], str, str]:
    manufacturer = normalize_text(row.get("mark"))
    model = normalize_text(row.get("model"))
    version = normalize_text(row.get("trim_name") or row.get("generation") or "")
    engine_type = normalize_text(row.get("fuel_type"))
    displacement_cc = parse_displacement_cc(row.get("displacement_cc"))
    year_month = parse_year_month(row.get("year_month"))
    hp = parse_hp(row.get("power_hp"))
    mn, vp = _motor_vin_from_pg_data(row.get("data"))
    return manufacturer, model, version, engine_type, displacement_cc, year_month, hp, mn, vp


def sync_from_postgres(
    pg_dsn: str,
    hp_db_path: Path,
    *,
    source_filter: str = "encar",
    include_rows_with_hp: bool = True,
    batch_size: int = 5000,
) -> Tuple[int, int]:
    hp_conn = connect(hp_db_path)
    ensure_schema(hp_conn)

    pg_conn = psycopg2.connect(pg_dsn)
    inserted_or_updated = 0
    with_hp = 0
    try:
        where_parts = ["mark IS NOT NULL", "model IS NOT NULL", "trim(mark) <> ''", "trim(model) <> ''"]
        params: list[Any] = []
        if source_filter and source_filter != "*":
            where_parts.append("source = %s")
            params.append(source_filter)
        if not include_rows_with_hp:
            where_parts.append("(power_hp IS NULL OR power_hp <= 0)")
        where_sql = " AND ".join(where_parts)
        sql = f"""
            SELECT mark, model, generation, trim_name, fuel_type, displacement_cc, year_month, power_hp, data
            FROM cars
            WHERE {where_sql}
            ORDER BY id ASC
        """

        with pg_conn.cursor(name="hp_catalog_pg", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.itersize = max(500, min(batch_size, 50000))
            cur.execute(sql, tuple(params))
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    (
                        manufacturer,
                        model,
                        version,
                        engine_type,
                        displacement_cc,
                        year_month,
                        hp,
                        motor_n,
                        vin_pf,
                    ) = _row_values(dict(row))
                    if not manufacturer or not model:
                        continue

                    norm_manufacturer = normalize_key_part(manufacturer)
                    norm_model = normalize_key_part(model)
                    norm_version = normalize_key_part(version)
                    norm_engine_type = normalize_key_part(engine_type)
                    llm_status = "done" if hp is not None else "pending"
                    llm_conf = 1.0 if hp is not None else None

                    hp_conn.execute(
                        """
                        INSERT INTO hp_catalog (
                            manufacturer, model, version, engine_type, displacement_cc, drive, year_month,
                            power_hp, power_kw,
                            norm_manufacturer, norm_model, norm_version, norm_engine_type,
                            motor_code_norm, vin_prefix,
                            llm_status, llm_reason, llm_attempts, llm_confidence, source, updated_at
                        ) VALUES (
                            ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, '', 0, ?, 'postgres',
                            strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        )
                        ON CONFLICT(norm_manufacturer, norm_model, norm_version, norm_engine_type,
                            COALESCE(displacement_cc, -1), year_month)
                        DO UPDATE SET
                            manufacturer = excluded.manufacturer,
                            model = excluded.model,
                            version = excluded.version,
                            engine_type = excluded.engine_type,
                            power_hp = COALESCE(excluded.power_hp, hp_catalog.power_hp),
                            power_kw = COALESCE(excluded.power_kw, hp_catalog.power_kw),
                            llm_confidence = COALESCE(excluded.llm_confidence, hp_catalog.llm_confidence),
                            motor_code_norm = COALESCE(NULLIF(excluded.motor_code_norm, ''),
                                hp_catalog.motor_code_norm),
                            vin_prefix = COALESCE(NULLIF(excluded.vin_prefix, ''), hp_catalog.vin_prefix),
                            llm_status = CASE
                                WHEN COALESCE(excluded.power_hp, hp_catalog.power_hp) IS NOT NULL THEN 'done'
                                WHEN hp_catalog.llm_status = 'done' THEN 'done'
                                ELSE hp_catalog.llm_status
                            END,
                            source = CASE
                                WHEN hp_catalog.source = 'csv' THEN hp_catalog.source
                                ELSE 'postgres'
                            END,
                            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        """,
                        (
                            manufacturer,
                            model,
                            version,
                            engine_type,
                            displacement_cc,
                            year_month,
                            hp,
                            hp_to_kw(hp),
                            norm_manufacturer,
                            norm_model,
                            norm_version,
                            norm_engine_type,
                            motor_n,
                            vin_pf,
                            llm_status,
                            llm_conf,
                        ),
                    )
                    inserted_or_updated += 1
                    if hp is not None:
                        with_hp += 1
                hp_conn.commit()
    finally:
        pg_conn.close()
        hp_conn.close()
    return inserted_or_updated, with_hp


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill hp_catalog.db from PostgreSQL cars table")
    p.add_argument("--dsn", default="", help="PostgreSQL DSN (fallback: DATABASE_URL or WRA_PG_DSN)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to hp_catalog.db")
    p.add_argument("--source", default="encar", help="cars.source filter (encar, che168, *, ...)")
    p.add_argument("--only-missing-hp", action="store_true", help="Import only rows without cars.power_hp")
    p.add_argument("--batch-size", type=int, default=5000, help="Read batch size from PostgreSQL")
    args = p.parse_args()

    dsn = _dsn(args.dsn)
    if not dsn:
        print("PostgreSQL DSN is required: --dsn or DATABASE_URL/WRA_PG_DSN")
        return 2

    n, with_hp = sync_from_postgres(
        dsn,
        args.db,
        source_filter=args.source,
        include_rows_with_hp=not args.only_missing_hp,
        batch_size=max(100, min(args.batch_size, 50000)),
    )
    print(f"hp_catalog synced from postgres: rows={n}, rows_with_hp={with_hp}, db={args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
