#!/usr/bin/env python3
"""
Импорт вердиктов оператора по конфликтам семейств hp_catalog в hp_family_conflict_verdict.

Ожидаемые колонки CSV (UTF-8, с BOM допустимо):
  - family_key — приоритетно; либо набор полей семьи как в отчёте hp_catalog_trim_power_conflict_report.py
  - verdict, notes, operator (notes/operator необязательны)

Пример строки после экспорта отчёта (можно редактировать одну строку на семью):
  family_key,operator_verdict,operator_verdict_notes,...
"""
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
    ensure_llm_prompt_cache_schema,
    ensure_schema,
    family_conflict_canonical_key,
    normalize_key_part,
    verdict_upsert,
)


def _family_key_from_row(row: dict[str, str]) -> str:
    raw = (row.get("family_key") or "").strip()
    if raw:
        return raw
    nm = normalize_key_part(row.get("family_nm") or "")
    nmodel = normalize_key_part(row.get("family_model") or "")
    eng = normalize_key_part(row.get("family_engine") or "")
    cc_s = str(row.get("family_cc") or "").strip()
    ym = str(row.get("family_ym") or "").strip()
    if not nm or not nmodel:
        return ""
    if not cc_s:
        dcc_sql = -1
    else:
        try:
            dcc_sql = int(cc_s)
        except ValueError:
            dcc_sql = -1
    return family_conflict_canonical_key(nm, nmodel, eng, dcc_sql, ym)


def _verdict_notes_op(row: dict[str, str]) -> tuple[str, str, str]:
    v = (row.get("verdict") or row.get("operator_verdict") or "").strip()
    notes = (row.get("notes") or row.get("operator_verdict_notes") or "").strip()
    op = (row.get("operator") or row.get("operator_verdict_author") or "").strip()
    return v, notes, op


def import_verdict_csv(csv_path: Path, db_path: Path) -> tuple[int, int]:
    skipped = inserted = 0
    conn = connect(db_path)
    ensure_schema(conn)
    ensure_llm_prompt_cache_schema(conn)
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return 0, 0
            for raw in reader:
                row = {str(k): str(raw.get(str(k)) if raw.get(str(k)) is not None else "").strip()
                       for k in (reader.fieldnames or [])}
                fk = _family_key_from_row(row)
                verdict, notes, operator = _verdict_notes_op(row)
                if not fk or not verdict:
                    skipped += 1
                    continue
                verdict_upsert(conn, family_key=fk, verdict=verdict, notes=notes, operator=operator)
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted, skipped


def main() -> int:
    p = argparse.ArgumentParser(description="Import operator verdicts for hp family conflicts into hp_catalog.db")
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = p.parse_args()
    if not args.csv.is_file():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 1
    n, skip = import_verdict_csv(args.csv, args.db)
    print(f"verdict_upsert rows={n} skipped_empty_key_or_verdict={skip} db={args.db}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
