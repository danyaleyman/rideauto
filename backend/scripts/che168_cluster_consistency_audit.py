#!/usr/bin/env python3
"""Проверка согласованности che168_cluster_registry ↔ cars.dedupe_canonical_car_id."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scraper_pipeline.che168.cluster_registry import _che168_numeric_rank  # noqa: E402


def _dsn(config_path: Path) -> str:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml and config_path.is_file():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            dsn = str((((cfg.get("storage") or {}).get("postgres") or {}).get("dsn") or "")).strip())
            if dsn:
                return dsn
        except Exception:
            pass
    return (os.environ.get("DATABASE_URL") or "").strip()


def main() -> int:
    import psycopg2
    import psycopg2.extras

    p = argparse.ArgumentParser(description="Che168 cluster registry vs dedupe_canonical audit")
    p.add_argument("--config", default="", help="YAML with storage.postgres.dsn")
    args = p.parse_args()

    dsn = _dsn(Path(args.config).expanduser().resolve()) if args.config else (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        print("Need DATABASE_URL or --config with dsn", file=sys.stderr)
        return 2

    clusters: Dict[str, List[str]] = {}
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cluster_key, car_id
                FROM che168_cluster_registry
                ORDER BY cluster_key, car_id
                """
            )
            for ck, cid in cur.fetchall() or []:
                if not ck or not cid:
                    continue
                clusters.setdefault(str(ck), []).append(str(cid))

    mismatch_rows: List[Dict[str, Any]] = []
    multi_keys = 0
    for ck, members in clusters.items():
        if len(members) < 2:
            continue
        multi_keys += 1
        canonical = min(members, key=_che168_numeric_rank)
        for m in members:
            exp: str | None = None if m == canonical else canonical
            mismatch_rows.append({"cluster_key": ck, "car_id": m, "expected_dedupe": exp})

    if not mismatch_rows:
        out = {
            "cluster_keys_with_2plus_members": multi_keys,
            "db_checked": 0,
            "mismatches": [],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    pairs = [(r["car_id"], r["expected_dedupe"]) for r in mismatch_rows]
    actual: Dict[str, Any] = {}
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT car_id, dedupe_canonical_car_id
                FROM cars
                WHERE car_id = ANY(%s)
                """,
                ([p[0] for p in pairs],),
            )
            for row in cur.fetchall() or []:
                actual[str(row["car_id"])] = row.get("dedupe_canonical_car_id")

    mismatches: List[Dict[str, Any]] = []
    for r in mismatch_rows:
        cid = r["car_id"]
        exp = r["expected_dedupe"]
        got = actual.get(cid)
        exp_s = str(exp) if exp is not None else None
        got_s = str(got) if got not in (None, "") else None
        if exp_s != got_s:
            mismatches.append({**r, "actual_dedupe": got_s})

    out = {
        "cluster_keys_with_2plus_members": multi_keys,
        "registry_rows_in_multi_clusters": len(mismatch_rows),
        "db_checked": len(actual),
        "mismatches": mismatches[:200],
        "mismatch_count": len(mismatches),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
