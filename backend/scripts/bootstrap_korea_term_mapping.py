#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Optional, Sequence, Set, Tuple

import psycopg2

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from localization.term_localizer import PgTermLocalizer  # noqa: E402

# (PostgreSQL cars.* column → term_translation_cache domain = column name).
PG_COLUMN_SPECS: Sequence[Tuple[str, str]] = (
    ("mark", "en"),
    ("model", "en"),
    ("generation", "en"),
    ("trim_name", "en"),
    ("drive_type", "en"),
    ("body_type", "ru"),
    ("fuel_type", "ru"),
    ("transmission_type", "ru"),
    ("color", "ru"),
)

# Объём JSON / отдельной колонки: (bucket ключ в terms → domain для PgTermLocalizer.translate, target_lang).
LINEAGE_SPECS: Sequence[Tuple[str, str, str]] = (
    ("model_group", "modelGroupName", "en"),
)


def _clean(v: object) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _push_term(bag: DefaultDict[str, Set[str]], domain: str, value: object) -> None:
    s = _clean(value)
    if s:
        bag[domain].add(s)


def _collect_from_csv(csv_path: Path, source_name: str) -> DefaultDict[str, Set[str]]:
    out: DefaultDict[str, Set[str]] = defaultdict(set)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            src = _clean(row.get("source")).lower()
            if source_name and src and src != source_name:
                continue
            for col, _tl in PG_COLUMN_SPECS:
                _push_term(out, col, row.get(col))

            raw = _clean(row.get("data"))
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            data = obj.get("data") if isinstance(obj, dict) and isinstance(obj.get("data"), dict) else None
            if not isinstance(data, dict):
                continue
            _push_term(out, "trim_name", data.get("gradeName") or data.get("configuration"))
            _push_term(out, "fuel_type", data.get("engine_type"))
            _push_term(out, "drive_type", data.get("prep_drive_type"))
            _push_term(out, "model_group", data.get("modelGroupName"))
    return out


def _collect_encar_model_group_pg(cur: Any, source_name: str, out: DefaultDict[str, Set[str]]) -> None:
    try:
        cur.execute(
            """
            SELECT DISTINCT encar_model_group
            FROM cars
            WHERE source = %s
              AND encar_model_group IS NOT NULL
              AND btrim(encar_model_group) <> ''
            """,
            (source_name,),
        )
        for (val,) in cur.fetchall():
            _push_term(out, "model_group", val)
    except Exception:
        pass


def _collect_from_db(dsn: str, source_name: str) -> DefaultDict[str, Set[str]]:
    out: DefaultDict[str, Set[str]] = defaultdict(set)
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            for col, _tl in PG_COLUMN_SPECS:
                cur.execute(
                    f"""
                    SELECT DISTINCT {col}
                    FROM cars
                    WHERE source = %s
                      AND {col} IS NOT NULL
                      AND btrim({col}) <> ''
                    """,
                    (source_name,),
                )
                for (val,) in cur.fetchall():
                    _push_term(out, col, val)
            _collect_encar_model_group_pg(cur, source_name, out)
    finally:
        conn.close()
    return out


def _translate_terms(terms: Dict[str, Set[str]], localizer: PgTermLocalizer) -> tuple[int, int]:
    total = 0
    translated = 0
    for col, target in PG_COLUMN_SPECS:
        values = sorted(terms.get(col, set()), key=lambda s: (len(s), s))
        if not values:
            continue
        for v in values:
            total += 1
            out = localizer.translate(v, target_lang=target, domain=col)
            if _clean(out) and _clean(out) != v:
                translated += 1
    for bucket, loc_domain, target in LINEAGE_SPECS:
        values = sorted(terms.get(bucket, set()), key=lambda s: (len(s), s))
        if not values:
            continue
        for v in values:
            total += 1
            out = localizer.translate(v, target_lang=target, domain=loc_domain)
            if _clean(out) and _clean(out) != v:
                translated += 1
    return total, translated


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bootstrap full Encar term mapping into term_translation_cache.")
    p.add_argument("--dsn", default=(os.environ.get("DATABASE_URL") or "").strip())
    p.add_argument("--csv", default="", help="Path to cars_korea.csv (optional alternative to DB)")
    p.add_argument("--source", default="encar", help="Cars source to map (default: encar)")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    dsn = (args.dsn or "").strip()
    csv_path = Path(args.csv).expanduser() if args.csv else None
    if not dsn and not csv_path:
        print("Provide --dsn (or DATABASE_URL) or --csv path.", file=sys.stderr)
        return 2
    if csv_path and not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 2

    if csv_path:
        terms = _collect_from_csv(csv_path, source_name=args.source.strip().lower())
        loc_dsn: Optional[str] = dsn if dsn else ""
    else:
        terms = _collect_from_db(dsn, source_name=args.source.strip().lower())
        loc_dsn = dsn

    if not any(terms.values()):
        print("No terms found for mapping.", file=sys.stderr)
        return 0

    if not (loc_dsn or "").strip():
        print("--dsn (or DATABASE_URL) required when using --csv so PgTermLocalizer can open Postgres.", file=sys.stderr)
        return 2

    localizer = PgTermLocalizer(loc_dsn)
    localizer.open()
    try:
        total, translated = _translate_terms(terms, localizer)
    finally:
        localizer.close()

    print(
        (
            f"Mapping done: total_terms={total} translated_changed={translated} "
            f"cache_hits={localizer.stats.cache_hits}"
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
