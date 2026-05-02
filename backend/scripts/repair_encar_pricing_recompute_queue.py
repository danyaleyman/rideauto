#!/usr/bin/env python3
"""Помечает Encar-строки на пересчёт цены: needs_pricing_recompute (эвристика encar_json_suggests_pricing_resync)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def _dsn(config_path: Path) -> str:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml and config_path.is_file():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            dsn = str(
                (((cfg.get("storage") or {}).get("postgres") or {}).get("dsn") or "").strip()
            )
            if dsn:
                return dsn
        except Exception:
            pass
    return (os.environ.get("DATABASE_URL") or "").strip()


def _fetch_encar_candidates(
    dsn: str,
    *,
    limit: int,
    car_ids: List[str] | None,
) -> List[Tuple[int, str, Dict[str, Any]]]:
    import psycopg2
    import psycopg2.extras

    if car_ids:
        q = """
        SELECT id, car_id, data
        FROM cars
        WHERE (source IS NULL OR lower(trim(source)) = 'encar')
          AND (car_id IS NULL OR car_id NOT LIKE 'dongchedi-%')
          AND car_id = ANY(%s)
        ORDER BY id ASC
        """
        params: Tuple[Any, ...] = (list(car_ids),)
    else:
        q = """
        SELECT id, car_id, data
        FROM cars
        WHERE (source IS NULL OR lower(trim(source)) = 'encar')
          AND (car_id IS NULL OR car_id NOT LIKE 'dongchedi-%')
        ORDER BY id ASC
        LIMIT %s
        """
        params = (limit,)
    out: List[Tuple[int, str, Dict[str, Any]]] = []
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, params)
            for row in cur.fetchall():
                data = row.get("data")
                if not isinstance(data, dict):
                    continue
                out.append((int(row["id"]), str(row["car_id"]), data))
    return out


def main() -> int:
    from catalog_encar_pricing import encar_json_suggests_pricing_resync

    p = argparse.ArgumentParser(description="Mark Encar rows needs_pricing_recompute from stale pricing JSON heuristics")
    p.add_argument("--config", default="scraper_config.yaml")
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--apply", action="store_true", help="UPDATE cars; default is dry-run")
    p.add_argument("--car-id", action="append", default=[], help="Restrict to car_id (repeatable)")
    args = p.parse_args()

    dsn = _dsn(Path(args.config).expanduser().resolve())
    if not dsn:
        print("DATABASE_URL / config storage.postgres.dsn required", file=sys.stderr)
        return 2

    rows = _fetch_encar_candidates(dsn, limit=max(1, args.limit), car_ids=args.car_id or None)
    to_mark: List[int] = []
    for rid, cid, data in rows:
        if encar_json_suggests_pricing_resync(data):
            to_mark.append(rid)

    print(f"scanned={len(rows)} mark={len(to_mark)} apply={args.apply}", flush=True)
    if not to_mark or not args.apply:
        for rid in to_mark[:50]:
            print(f"  would_mark id={rid}", flush=True)
        if len(to_mark) > 50:
            print(f"  ... and {len(to_mark) - 50} more", flush=True)
        return 0

    import psycopg2

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cars
                SET needs_pricing_recompute = TRUE, updated_at = now()
                WHERE id = ANY(%s)
                """,
                (to_mark,),
            )
            n = cur.rowcount
        conn.commit()
    print(f"updated rows={n}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
