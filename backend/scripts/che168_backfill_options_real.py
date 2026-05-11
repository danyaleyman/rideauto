#!/usr/bin/env python3
"""Пересчёт options_real / che168_recommended_options из raw_envelope.sources.specconfig (без повторного HTTP)."""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, List, Tuple

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
            dsn = str((((cfg.get("storage") or {}).get("postgres") or {}).get("dsn") or "").strip())
            if dsn:
                return dsn
        except Exception:
            pass
    return (os.environ.get("DATABASE_URL") or "").strip()


def _fetch_rows(dsn: str, *, limit: int, car_ids: List[str] | None) -> List[Tuple[int, str, dict[str, Any]]]:
    import psycopg2
    import psycopg2.extras

    if car_ids:
        q = """
        SELECT id, car_id, data
        FROM cars
        WHERE lower(trim(source)) = 'che168'
          AND car_id = ANY(%s)
        ORDER BY id ASC
        """
        params: Tuple[Any, ...] = (list(car_ids),)
    else:
        q = """
        SELECT id, car_id, data
        FROM cars
        WHERE lower(trim(source)) = 'che168'
        ORDER BY id ASC
        LIMIT %s
        """
        params = (max(1, limit),)
    out: List[Tuple[int, str, dict[str, Any]]] = []
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, params)
            for row in cur.fetchall():
                data = row.get("data")
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                if not isinstance(data, dict):
                    continue
                out.append((int(row["id"]), str(row["car_id"]), data))
    return out


def _specconfig_from_data(data: dict[str, Any]) -> dict[str, Any] | None:
    env = data.get("raw_envelope")
    if not isinstance(env, dict):
        return None
    sources = env.get("sources")
    if not isinstance(sources, dict):
        return None
    sc = sources.get("specconfig")
    return sc if isinstance(sc, dict) else None


def main() -> int:
    from scraper_pipeline.che168.parser import extract_che168_options_real_from_specconfig

    p = argparse.ArgumentParser(
        description="Заполнить data.options_real и data.che168_recommended_options из сохранённого specconfig в raw_envelope",
    )
    p.add_argument("--config", default="che168_scraper.yaml")
    p.add_argument("--dsn", default="", help="Override PostgreSQL DSN")
    p.add_argument("--limit", type=int, default=10_000)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--car-id", action="append", default=[], help="Только эти car_id (повторяемый флаг)")
    args = p.parse_args()

    dsn = (args.dsn or "").strip() or _dsn(Path(args.config).expanduser().resolve())
    if not dsn:
        print("Нужен DSN: --dsn или DATABASE_URL / storage.postgres.dsn в конфиге", file=sys.stderr)
        return 2

    rows = _fetch_rows(dsn, limit=max(1, args.limit), car_ids=args.car_id or None)
    updates: List[Tuple[int, dict[str, Any]]] = []
    skipped_no_spec = 0
    skipped_empty = 0
    for rid, cid, data in rows:
        sc = _specconfig_from_data(data)
        if sc is None:
            skipped_no_spec += 1
            continue
        opts = extract_che168_options_real_from_specconfig(sc)
        if not opts:
            skipped_empty += 1
            continue
        new_data = copy.deepcopy(data)
        new_data["options_real"] = opts
        new_data["che168_recommended_options"] = opts
        updates.append((rid, new_data))

    print(
        f"scanned={len(rows)} to_update={len(updates)} no_specconfig={skipped_no_spec} empty_options={skipped_empty} apply={args.apply}",
        flush=True,
    )
    if not args.apply:
        for rid, nd in updates[:15]:
            n = len(nd.get("options_real") or [])
            print(f"  would_update id={rid} options={n}", flush=True)
        if len(updates) > 15:
            print(f"  ... and {len(updates) - 15} more", flush=True)
        return 0

    import psycopg2.extras

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            for rid, nd in updates:
                cur.execute(
                    "UPDATE cars SET data = %s, updated_at = now() WHERE id = %s",
                    (psycopg2.extras.Json(nd), rid),
                )
        conn.commit()
    print(f"updated={len(updates)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
