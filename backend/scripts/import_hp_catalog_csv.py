#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

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


def _row_value(row: dict, *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return normalize_text(row[key])
    return ""


def import_csv(csv_path: Path, db_path: Path) -> tuple[int, int]:
    conn = connect(db_path)
    ensure_schema(conn)
    processed = 0
    with_hp = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            manufacturer = _row_value(row, "manufacturer", "mark")
            model = _row_value(row, "model")
            version = _row_value(row, "version", "generation", "gradeName", "configuration")
            engine_type = _row_value(row, "engine_type", "fuel_type")
            drive = _row_value(row, "drive", "drive_type")
            year_month = parse_year_month(_row_value(row, "year", "yearMonth", "year_month"))
            displacement_cc = parse_displacement_cc(_row_value(row, "displacement", "displacement_cc"))

            if not manufacturer or not model:
                continue
            processed += 1

            hp = parse_hp(_row_value(row, "power_hp", "hp", "power"))
            kw_raw = _row_value(row, "kW", "kw", "power_kw")
            kw = None
            if kw_raw:
                try:
                    kw = round(float(kw_raw.replace(",", ".")), 1)
                except ValueError:
                    kw = None
            if hp is not None and kw is None:
                kw = hp_to_kw(hp)

            norm_manufacturer = normalize_key_part(manufacturer)
            norm_model = normalize_key_part(model)
            norm_version = normalize_key_part(version)
            norm_engine_type = normalize_key_part(engine_type)

            llm_status = "done" if hp is not None else "pending"

            conn.execute(
                """
                INSERT INTO hp_catalog (
                    manufacturer, model, version, engine_type, displacement_cc, drive, year_month,
                    power_hp, power_kw,
                    norm_manufacturer, norm_model, norm_version, norm_engine_type,
                    llm_status, llm_reason, llm_attempts, source, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0, 'csv',
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                )
                ON CONFLICT
                DO UPDATE SET
                    manufacturer = excluded.manufacturer,
                    model = excluded.model,
                    version = excluded.version,
                    engine_type = excluded.engine_type,
                    drive = excluded.drive,
                    power_hp = COALESCE(excluded.power_hp, hp_catalog.power_hp),
                    power_kw = COALESCE(excluded.power_kw, hp_catalog.power_kw),
                    llm_status = CASE
                        WHEN COALESCE(excluded.power_hp, hp_catalog.power_hp) IS NOT NULL THEN 'done'
                        ELSE hp_catalog.llm_status
                    END,
                    source = 'csv',
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                """,
                (
                    manufacturer,
                    model,
                    version,
                    engine_type,
                    displacement_cc,
                    drive,
                    year_month,
                    hp,
                    kw,
                    norm_manufacturer,
                    norm_model,
                    norm_version,
                    norm_engine_type,
                    llm_status,
                ),
            )
            if hp is not None:
                with_hp += 1

    conn.commit()
    conn.close()
    return processed, with_hp


def main() -> int:
    p = argparse.ArgumentParser(description="Import unique car rows into hp_catalog.db")
    p.add_argument("--csv", type=Path, required=True, help="Path to CSV (cars_hp.csv)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to hp_catalog.db")
    args = p.parse_args()

    if not args.csv.is_file():
        print(f"CSV not found: {args.csv}")
        return 1

    processed, with_hp = import_csv(args.csv, args.db)
    print(f"Imported into {args.db}")
    print(f"  rows_processed: {processed}")
    print(f"  rows_with_hp_present_in_csv: {with_hp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
