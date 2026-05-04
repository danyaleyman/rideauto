#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import psycopg2
import psycopg2.extras

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from localization.term_localizer import facet_canonical_english  # noqa: E402

_CJK_RE = re.compile(r"[\u4e00-\u9fff\uac00-\ud7af]+")
_SPACE_RE = re.compile(r"\s+")


def _clean(v: object) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _normalize_en(value: object, domain: str) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    out = _clean(facet_canonical_english(raw, domain)) or raw
    out = _SPACE_RE.sub(" ", out).strip()
    # Китай/корейский в финальном лейбле не держим.
    out = _SPACE_RE.sub(" ", _CJK_RE.sub(" ", out)).strip()
    # Схлопываем дубли вида "Cadillac Cadillac XTS".
    out = re.sub(r"^([A-Za-z0-9&\-]+)\s+\1\b", r"\1", out, flags=re.IGNORECASE)
    return out or raw


def _title(mark: str, model: str, generation: str) -> str:
    parts: List[str] = []
    for x in (mark, model, generation):
        t = _clean(x)
        if t and (not parts or parts[-1].lower() != t.lower()):
            parts.append(t)
    return " ".join(parts).strip()


def _iter_rows(conn: psycopg2.extensions.connection, batch_size: int) -> Iterable[List[Dict[str, Any]]]:
    with conn.cursor(name="china_name_backfill", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.itersize = max(256, min(batch_size, 5000))
        cur.execute(
            """
            SELECT id, mark, model, generation, trim_name, data
            FROM cars
            WHERE source = 'che168'
            ORDER BY id ASC
            """
        )
        batch: List[Dict[str, Any]] = []
        for row in cur:
            batch.append(dict(row))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def _transform_row(row: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    raw_data = row.get("data")
    if isinstance(raw_data, str):
        try:
            data = json.loads(raw_data)
        except Exception:
            data = {}
    elif isinstance(raw_data, dict):
        data = dict(raw_data)
    else:
        data = {}

    mark_src = _clean(data.get("mark") or row.get("mark"))
    model_src = _clean(data.get("model") or row.get("model"))
    gen_src = _clean(data.get("generation") or row.get("generation"))
    trim_src = _clean(data.get("trim_name") or data.get("gradeName") or data.get("configuration") or row.get("trim_name"))

    mark = _normalize_en(mark_src, "mark")
    model = _normalize_en(model_src, "model")
    generation = _normalize_en(gen_src, "generation")
    trim = _normalize_en(trim_src, "trim_name")

    changed = False

    def _set(obj: Dict[str, Any], key: str, value: str) -> None:
        nonlocal changed
        if not value:
            return
        if _clean(obj.get(key)) != value:
            obj[key] = value
            changed = True

    _set(data, "mark", mark)
    _set(data, "mark_en", mark)
    _set(data, "model", model)
    _set(data, "model_en", model)
    _set(data, "generation", generation)
    _set(data, "generation_en", generation)
    _set(data, "trim_name", trim)
    _set(data, "trim_name_en", trim)
    _set(data, "configuration", trim)
    _set(data, "configuration_en", trim)
    _set(data, "gradeName", trim)
    _set(data, "gradeName_en", trim)

    t = _title(mark, model, generation)
    if t and _clean(data.get("title_en")) != t:
        data["title_en"] = t
        changed = True

    payload = {
        "id": int(row["id"]),
        "mark": mark or None,
        "model": model or None,
        "generation": generation or None,
        "trim_name": trim or None,
        "data": psycopg2.extras.Json(data),
    }
    return changed, payload


def _apply_batch(conn: psycopg2.extensions.connection, patch_rows: List[Dict[str, Any]]) -> None:
    if not patch_rows:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            UPDATE cars
            SET mark = %(mark)s,
                model = %(model)s,
                generation = %(generation)s,
                trim_name = %(trim_name)s,
                data = %(data)s,
                needs_pricing_recompute = TRUE,
                updated_at = now()
            WHERE id = %(id)s
            """,
            patch_rows,
            page_size=500,
        )
    conn.commit()


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill canonical EN names for all China cars.")
    p.add_argument("--dsn", default=(os.environ.get("DATABASE_URL") or "").strip())
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    dsn = _clean(args.dsn)
    if not dsn:
        print("Provide --dsn or DATABASE_URL", file=sys.stderr)
        return 2

    conn = psycopg2.connect(dsn)
    scanned = 0
    changed = 0
    try:
        for chunk in _iter_rows(conn, max(100, args.batch_size)):
            patch_rows: List[Dict[str, Any]] = []
            for row in chunk:
                scanned += 1
                is_changed, payload = _transform_row(row)
                if is_changed:
                    changed += 1
                    patch_rows.append(payload)
            if patch_rows and not args.dry_run:
                _apply_batch(conn, patch_rows)
            if scanned % 10000 == 0:
                print(f"progress scanned={scanned} changed={changed}", flush=True)
    finally:
        conn.close()

    print(f"done scanned={scanned} changed={changed} dry_run={args.dry_run}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

