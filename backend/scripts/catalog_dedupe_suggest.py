#!/usr/bin/env python3
"""
Batch-поиск кандидатов на слияние дублей по тому же ключу, что и Meilisearch (catalog_dedupe_key).

Только отчёт (dry-run по умолчанию). Связать пары: scripts/catalog_dedupe_link.py.

Пример:
  python scripts/catalog_dedupe_suggest.py --dsn "$DATABASE_URL" --format jsonl > dup_report.jsonl
  python scripts/catalog_dedupe_suggest.py --format table --min-size 2 --no-id-keys
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Tuple

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from catalog_dedupe import catalog_dedupe_key, listing_json_inner_from_cars_data  # noqa: E402


def _parse_ts(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, datetime):
        return v.timestamp()
    try:
        return float(v)
    except Exception:
        return 0.0


def main() -> None:
    p = argparse.ArgumentParser(description="Report duplicate listing groups by catalog_dedupe_key")
    p.add_argument("--dsn", default="", help="PostgreSQL URI или DATABASE_URL")
    p.add_argument("--format", choices=("jsonl", "table", "json"), default="jsonl")
    p.add_argument("--min-size", type=int, default=2, help="Минимум листингов в группе")
    p.add_argument(
        "--include-id-keys",
        action="store_true",
        help="Включать группы с ключом id:* (шумно; обычно только vin: и source:inner)",
    )
    p.add_argument("--limit-rows", type=int, default=0, help="Остановиться после N строк (отладка)")
    args = p.parse_args()

    dsn = (args.dsn or "").strip() or os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("need --dsn or DATABASE_URL", file=sys.stderr)
        sys.exit(2)

    groups: DefaultDict[str, List[Tuple[str, float, str]]] = defaultdict(list)
    # car_id, updated_at ts, source

    conn = psycopg2.connect(dsn)
    try:
        q = """
            SELECT car_id, source, data, updated_at
            FROM cars
            WHERE dedupe_canonical_car_id IS NULL
            ORDER BY car_id
        """
        with conn.cursor(name="wra_dedupe_suggest", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.itersize = 4096
            cur.execute(q)
            n = 0
            for row in cur:
                cid = str(row.get("car_id") or "").strip()
                if not cid:
                    continue
                src = row.get("source")
                inner = listing_json_inner_from_cars_data(row.get("data"))
                key = catalog_dedupe_key(cid, str(src) if src is not None else None, inner)
                ts = _parse_ts(row.get("updated_at"))
                groups[key].append((cid, ts, str(src or "")))
                n += 1
                if args.limit_rows and n >= args.limit_rows:
                    break
    finally:
        conn.close()

    reports: List[Dict[str, Any]] = []
    for key, items in groups.items():
        if len(items) < args.min_size:
            continue
        if not args.include_id_keys and key.startswith("id:"):
            continue
        items_sorted = sorted(items, key=lambda x: (-x[1], x[0]))
        canonical = items_sorted[0][0]
        dups = [x[0] for x in items_sorted[1:]]
        reports.append(
            {
                "dedupe_key": key,
                "count": len(items),
                "canonical_car_id": canonical,
                "duplicate_car_ids": dups,
                "members": [{"car_id": x[0], "updated_at_ts": x[1], "source": x[2]} for x in items_sorted],
            }
        )

    reports.sort(key=lambda r: (-r["count"], r["dedupe_key"]))

    if args.format == "json":
        json.dump({"groups": reports, "total_groups": len(reports)}, sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif args.format == "jsonl":
        for r in reports:
            print(json.dumps(r, ensure_ascii=False))
    else:
        for r in reports:
            print(f"{r['dedupe_key']}\t{r['count']}\tcanonical={r['canonical_car_id']}\tdups={','.join(r['duplicate_car_ids'])}")


if __name__ == "__main__":
    main()
