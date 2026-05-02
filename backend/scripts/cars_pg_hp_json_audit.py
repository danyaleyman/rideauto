#!/usr/bin/env python3
"""Сводка расхождения cars.power_hp (колонка) и nested JSON power в payload."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _dsn(cli: str) -> str:
    return (cli or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN") or "").strip()


def _parse_hp(val: object) -> int | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        hp = int(val)
        return hp if hp > 0 else None
    s = "".join(ch for ch in str(val) if ch.isdigit() or ch in ".,")
    if not s:
        return None
    try:
        hp = int(float(s.replace(",", ".")))
        return hp if hp > 0 else None
    except ValueError:
        return None


def _nested_power(data_blob: dict) -> int | None:
    inner = data_blob.get("data")
    if not isinstance(inner, dict):
        return None
    return _parse_hp(inner.get("power") or inner.get("power_hp") or inner.get("horsepower"))


def main() -> int:
    import psycopg2
    import psycopg2.extras

    p = argparse.ArgumentParser(description="Postgres audit: колонка power_hp vs data JSON power")
    p.add_argument("--dsn", default="")
    p.add_argument("--source", default="", help="Фильтр cars.source (пусто = все)")
    p.add_argument("--limit", type=int, default=50000)
    p.add_argument("--csv", type=Path, default=None, help="Выгрузить только проблемные строки")
    args = p.parse_args()

    dsn = _dsn(args.dsn)
    if not dsn:
        print("Need --dsn or DATABASE_URL", file=sys.stderr)
        return 2

    where = ""
    qp: tuple = ()
    if args.source.strip():
        where = "WHERE source = %s "
        qp = (args.source.strip(),)

    sql = f"""
        SELECT id, car_id, source, power_hp, data
        FROM cars
        {where}
        ORDER BY id ASC
        LIMIT %s
    """

    mism = mismatch_no_col = mismatch_no_js = aligned = skipped = 0
    problem_rows: list[dict[str, object]] = []

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, qp + (max(100, args.limit),))
            for row in cur:
                col_hp = _parse_hp(row.get("power_hp"))

                jb = row.get("data") or {}
                if isinstance(jb, (bytes, memoryview)):
                    try:
                        jb = json.loads(bytes(jb).decode("utf-8"))
                    except Exception:
                        jb = {}
                elif isinstance(jb, str):
                    try:
                        jb = json.loads(jb)
                    except json.JSONDecodeError:
                        jb = {}

                js_hp = _nested_power(jb if isinstance(jb, dict) else {})

                rec: dict[str, object] = {
                    "id": row.get("id"),
                    "car_id": row.get("car_id"),
                    "source": row.get("source"),
                    "power_hp_column": col_hp,
                    "power_hp_nested_json": js_hp,
                }

                why = ""

                if col_hp is None and js_hp is None:
                    skipped += 1
                    continue
                if col_hp is None and js_hp is not None:
                    mismatch_no_col += 1
                    why = "column_null_json_has_hp"
                elif col_hp is not None and js_hp is None:
                    mismatch_no_js += 1
                    why = "json_null_column_has_hp"
                elif int(col_hp) != int(js_hp):
                    mism += 1
                    why = "different_values"
                else:
                    aligned += 1

                if why:
                    rec["reason"] = why
                    problem_rows.append(rec)

    finally:
        conn.close()

    print(
        json.dumps(
            {
                "scanned_rows": mismatch_no_col + mismatch_no_js + mism + aligned + skipped,
                "aligned": aligned,
                "skipped_both_blank": skipped,
                "mismatch_numbers": mism,
                "column_null_json_power": mismatch_no_col,
                "column_power_json_blank": mismatch_no_js,
                "problem_rows_count": len(problem_rows),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    if args.csv:
        outp = Path(args.csv)
        outp.parent.mkdir(parents=True, exist_ok=True)
        fields = ["id", "car_id", "source", "power_hp_column", "power_hp_nested_json", "reason"]
        with outp.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(problem_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
