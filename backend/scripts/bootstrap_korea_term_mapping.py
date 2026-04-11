#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Set

import psycopg2

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from localization.term_localizer import PgTermLocalizer  # noqa: E402


DOMAIN_SPECS = (
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
            for domain, _target in DOMAIN_SPECS:
                _push_term(out, domain, row.get(domain))

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
    return out


def _collect_from_db(dsn: str, source_name: str) -> DefaultDict[str, Set[str]]:
    out: DefaultDict[str, Set[str]] = defaultdict(set)
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            for domain, _target in DOMAIN_SPECS:
                cur.execute(
                    f"""
                    SELECT DISTINCT {domain}
                    FROM cars
                    WHERE source = %s
                      AND {domain} IS NOT NULL
                      AND btrim({domain}) <> ''
                    """,
                    (source_name,),
                )
                for (val,) in cur.fetchall():
                    _push_term(out, domain, val)
    finally:
        conn.close()
    return out


def _translate_terms(terms: Dict[str, Set[str]], localizer: PgTermLocalizer) -> tuple[int, int]:
    total = 0
    translated = 0
    for domain, target in DOMAIN_SPECS:
        values = sorted(terms.get(domain, set()), key=lambda s: (len(s), s))
        if not values:
            continue
        for v in values:
            total += 1
            out = localizer.translate(v, target_lang=target, domain=domain)
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
    else:
        terms = _collect_from_db(dsn, source_name=args.source.strip().lower())

    if not any(terms.values()):
        print("No terms found for mapping.", file=sys.stderr)
        return 0

    localizer = PgTermLocalizer(dsn)
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
