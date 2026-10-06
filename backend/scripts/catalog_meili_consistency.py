#!/usr/bin/env python3
"""Meili consistency gate: outbox backlog + PG vs Meili ratio (ADR 0004).

Exit 0 OK, 2 soft warn (unless --strict), 3 hard fail (empty index / huge backlog).

Env:
  DATABASE_URL / SYNC_PG_DSN
  WRA_MEILISEARCH_URL, MEILI_MASTER_KEY
  WRA_MEILI_LIVE_INDEX
  WRA_MEILI_OUTBOX_WARN=500
  WRA_MEILI_OUTBOX_FAIL=5000
  WRA_CATALOG_MEILI_PG_RATIO_MIN=0.85
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional


def _env(*keys: str, default: str = "") -> str:
    for k in keys:
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    return default


def _pg(dsn: str) -> tuple[int, int]:
    import psycopg2

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cars WHERE dedupe_canonical_car_id IS NULL")
            active = int(cur.fetchone()[0] or 0)
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM meili_sync_outbox WHERE processed_at IS NULL"
                )
                pending = int(cur.fetchone()[0] or 0)
            except Exception:
                conn.rollback()
                pending = -1
            return active, pending
    finally:
        conn.close()


def _meili_docs(url: str, key: str, index: str) -> Optional[int]:
    req = urllib.request.Request(url.rstrip("/") + f"/indexes/{index}/stats")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return int(data.get("numberOfDocuments") or data.get("number_of_documents") or 0)
    except Exception as e:
        print(f"meili stats error: {e}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--textfile", default=os.environ.get("WRA_MEILI_CONSISTENCY_TEXTFILE", ""))
    args = ap.parse_args()
    dsn = (args.dsn or "").strip() or _env("DATABASE_URL", "SYNC_PG_DSN", "WRA_PG_DSN")
    if not dsn:
        print("need DATABASE_URL", file=sys.stderr)
        return 2

    warn_n = int(_env("WRA_MEILI_OUTBOX_WARN", default="500") or "500")
    fail_n = int(_env("WRA_MEILI_OUTBOX_FAIL", default="5000") or "5000")
    ratio_min = float(_env("WRA_CATALOG_MEILI_PG_RATIO_MIN", default="0.85") or "0.85")

    active, pending = _pg(dsn)
    meili_url = _env("WRA_MEILISEARCH_URL", default="http://127.0.0.1:7700")
    meili_key = _env("MEILI_MASTER_KEY", "WRA_MEILISEARCH_KEY")
    index = _env("WRA_MEILI_LIVE_INDEX", "WRA_MEILISEARCH_INDEX", default="cars")
    docs = _meili_docs(meili_url, meili_key, index)

    ratio = (float(docs) / float(active)) if docs is not None and active > 0 else None
    empty = 1 if docs == 0 else 0
    print(
        f"meili_consistency: pg_active={active} meili_docs={docs} outbox_pending={pending} "
        f"ratio={ratio}",
        flush=True,
    )

    textfile = (args.textfile or "").strip()
    if textfile:
        lines = [
            "# HELP wra_meili_outbox_pending Unprocessed meili_sync_outbox rows",
            "# TYPE wra_meili_outbox_pending gauge",
            f"wra_meili_outbox_pending {pending}",
            "# HELP wra_meili_consistency_check_unixtime Last consistency check",
            "# TYPE wra_meili_consistency_check_unixtime gauge",
            f"wra_meili_consistency_check_unixtime {int(time.time())}",
            "",
        ]
        out = Path(textfile)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text("\n".join(lines), encoding="utf-8")
        tmp.replace(out)

    hard = False
    soft = False
    if docs == 0 and active > 100:
        hard = True
        print("FAIL: live Meili empty while PG has rows", file=sys.stderr)
    if pending >= fail_n:
        hard = True
        print(f"FAIL: outbox backlog {pending} >= {fail_n}", file=sys.stderr)
    elif pending >= warn_n:
        soft = True
        print(f"WARN: outbox backlog {pending} >= {warn_n}", file=sys.stderr)
    if ratio is not None and active > 1000 and ratio < ratio_min:
        soft = True
        print(f"WARN: meili/pg ratio {ratio:.3f} < {ratio_min}", file=sys.stderr)

    if hard:
        return 3
    if soft and args.strict:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
