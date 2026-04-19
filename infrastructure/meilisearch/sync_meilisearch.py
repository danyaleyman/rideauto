#!/usr/bin/env python3
"""
Full or incremental sync: PostgreSQL `cars` → Meilisearch index `cars`.

Field mapping (Meilisearch document):
  brand       ← cars.mark
  model       ← cars.model
  price       ← cars.price_rub
  year        ← cars.year
  color       ← cars.color
  body_type   ← cars.body_type
  mileage     ← cars.mileage_km
  fuel        ← cars.fuel_type  (Encar `engine_type`, UI «топливо»)

Primary key: document `id` = cars.car_id (string).

Usage:
  python sync_meilisearch.py \\
    --pg-dsn "postgresql://user:pass@localhost:5432/wra" \\
    --meili-url "http://127.0.0.1:7700" \\
    --meili-key "$MEILI_MASTER_KEY" \\
    --settings ./index_settings.json

Optional:
  --batch-size 2000
  --index-name cars
  --settings-only
  --recreate-index
  --since 2025-01-01T00:00:00+00:00
  --no-wait-batches

Requires:
  pip install meilisearch psycopg2-binary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

try:
    from meilisearch import Client
    from meilisearch.errors import MeilisearchApiError
except ImportError:
    print("Install meilisearch: pip install meilisearch", file=sys.stderr)
    sys.exit(1)


def _optional_since(raw: Optional[str]) -> Optional[datetime]:
    if raw is None or not str(raw).strip():
        return None
    s = str(raw).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"invalid --since datetime: {raw!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fmt_ts_for_meili(dt: Optional[Any]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return d.isoformat().replace("+00:00", "Z")
    return str(dt)


_MODEL_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _parse_int_km(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        if isinstance(v, str):
            s = v.strip().replace("\u00a0", " ").replace(" ", "").replace(",", "").replace("'", "")
            if not s:
                return None
            return int(float(s))
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _year_for_document(row: Dict[str, Any]) -> Optional[int]:
    """Год в индексе: колонка cars.year или из year_month (YYYYMM), иначе None."""
    if row.get("year") is not None and str(row.get("year")).strip() != "":
        try:
            y = int(row["year"])
            if y > 0:
                return y
        except (TypeError, ValueError):
            pass
    ym = row.get("year_month")
    if ym is not None and str(ym).strip() != "":
        try:
            iv = int(ym)
            if iv >= 190001:
                return iv // 100
        except (TypeError, ValueError):
            pass
    return None


def _mileage_from_row(row: Dict[str, Any]) -> Optional[int]:
    km = _parse_int_km(row.get("mileage_km"))
    if km is not None:
        return km
    raw = row.get("data")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    if isinstance(raw, dict):
        return _parse_int_km(raw.get("km_age"))
    return None


def _model_group(model: str) -> str:
    s = (model or "").strip()
    if not s:
        return s
    prev = s
    while True:
        nxt = _MODEL_TRAILING_PAREN_RE.sub("", prev).strip()
        if not nxt or nxt == prev:
            break
        prev = nxt
    return prev or s


def row_to_document(row: Dict[str, Any]) -> Dict[str, Any]:
    car_id = row.get("car_id")
    if not car_id:
        raise ValueError("row missing car_id")

    doc: Dict[str, Any] = {
        "id": str(car_id),
        "pg_id": int(row["pg_id"]),
        "car_id": str(car_id),
        "brand": (row.get("mark") or "").strip(),
        "model": (row.get("model") or "").strip(),
        "model_group": _model_group((row.get("model") or "").strip()),
        "fuel": (row.get("fuel_type") or "").strip(),
        "color": (row.get("color") or "").strip(),
        "body_type": (row.get("body_type") or "").strip(),
        "generation": (row.get("generation") or "").strip(),
        "trim": (row.get("trim_name") or "").strip(),
        "transmission": (row.get("transmission_type") or "").strip(),
        "drive_type": (row.get("drive_type") or "").strip(),
    }

    src = row.get("source")
    if src is not None and str(src).strip():
        doc["source"] = str(src).strip()

    if row.get("price_rub") is not None:
        doc["price"] = float(row["price_rub"])
    yr = _year_for_document(row)
    if yr is not None:
        doc["year"] = int(yr)
    m_km = _mileage_from_row(row)
    if m_km is not None:
        doc["mileage"] = int(m_km)
    if row.get("year_month") is not None:
        doc["year_month"] = int(row["year_month"])

    updated = _fmt_ts_for_meili(row.get("updated_at"))
    if updated:
        doc["updated_at"] = updated

    listed = _fmt_ts_for_meili(row.get("created_at"))
    if listed:
        doc["catalog_created_at"] = listed

    return doc


def load_settings(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("index settings JSON must be an object")
    return data


def ensure_index(client: Client, uid: str, *, recreate: bool) -> None:
    if recreate:
        try:
            task = client.delete_index(uid)
            client.wait_for_task(task.task_uid, timeout_in_ms=600_000)
        except MeilisearchApiError:
            pass
    try:
        client.get_index(uid)
    except MeilisearchApiError:
        task = client.create_index(uid, {"primaryKey": "id"})
        client.wait_for_task(task.task_uid, timeout_in_ms=600_000)


def apply_settings(client: Client, uid: str, settings: Dict[str, Any]) -> None:
    index = client.index(uid)
    task = index.update_settings(settings)
    client.wait_for_task(task.task_uid, timeout_in_ms=600_000)


def iter_car_rows(
    dsn: str,
    *,
    since: Optional[datetime],
    batch_size: int,
):
    conn = psycopg2.connect(dsn)
    try:
        q = """
            SELECT
                c.id AS pg_id,
                c.car_id,
                c.mark,
                c.model,
                c.generation,
                c.trim_name,
                c.fuel_type,
                c.body_type,
                c.transmission_type,
                c.drive_type,
                c.color,
                c.price_rub,
                c.year,
                c.year_month,
                c.mileage_km,
                c.data,
                c.source,
                c.updated_at,
                c.created_at
            FROM cars AS c
            WHERE (%s::timestamptz IS NULL OR c.updated_at >= %s::timestamptz)
            ORDER BY c.id ASC
        """
        itersize = max(256, min(batch_size, 5000))
        with conn.cursor(name="wra_meili_sync", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.itersize = itersize
            cur.execute(q, (since, since))
            for row in cur:
                yield dict(row)
    finally:
        conn.close()


def push_batches(
    client: Client,
    uid: str,
    dsn: str,
    *,
    since: Optional[datetime],
    batch_size: int,
    wait_each_batch: bool,
) -> int:
    index = client.index(uid)
    total = 0
    batch: List[Dict[str, Any]] = []

    for row in iter_car_rows(dsn, since=since, batch_size=batch_size):
        try:
            batch.append(row_to_document(row))
        except ValueError:
            continue
        if len(batch) >= batch_size:
            task = index.add_documents(batch)
            if wait_each_batch:
                client.wait_for_task(task.task_uid, timeout_in_ms=1_800_000)
            total += len(batch)
            batch.clear()

    if batch:
        task = index.add_documents(batch)
        if wait_each_batch:
            client.wait_for_task(task.task_uid, timeout_in_ms=1_800_000)
        total += len(batch)

    return total


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Sync PostgreSQL cars → Meilisearch")
    parser.add_argument("--pg-dsn", default="", help="PostgreSQL connection URI")
    parser.add_argument("--meili-url", default="http://127.0.0.1:7700", help="Meilisearch server URL")
    parser.add_argument("--meili-key", default="", help="Meilisearch API key (Bearer)")
    parser.add_argument("--index-name", default="cars", help="Meilisearch index UID")
    parser.add_argument(
        "--settings",
        type=Path,
        default=here / "index_settings.json",
        help="PATCH body for /indexes/{uid}/settings",
    )
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--settings-only", action="store_true", help="Apply settings only (no documents)")
    parser.add_argument("--recreate-index", action="store_true", help="Delete index UID if it exists, then recreate")
    parser.add_argument("--since", default=None, help="Only rows with updated_at >= this ISO-8601 instant")
    parser.add_argument(
        "--no-wait-batches",
        action="store_true",
        help="Do not wait for Meilisearch between batches (faster; poll tasks in /tasks)",
    )
    args = parser.parse_args()

    settings_path = args.settings
    if not settings_path.is_file():
        parser.error(f"settings file not found: {settings_path}")

    try:
        since_dt = _optional_since(args.since)
    except ValueError as e:
        parser.error(str(e))

    if not args.pg_dsn and not args.settings_only:
        parser.error("--pg-dsn is required unless --settings-only")

    settings = load_settings(settings_path)
    client = Client(args.meili_url, args.meili_key or None)

    ensure_index(client, args.index_name, recreate=args.recreate_index)
    apply_settings(client, args.index_name, settings)

    if args.settings_only:
        print(f"settings applied to index {args.index_name!r}", flush=True)
        return

    assert args.pg_dsn
    n = push_batches(
        client,
        args.index_name,
        args.pg_dsn,
        since=since_dt,
        batch_size=max(1, min(args.batch_size, 50_000)),
        wait_each_batch=not args.no_wait_batches,
    )
    print(f"synced document batches (upsert count): {n}", flush=True)


if __name__ == "__main__":
    main()

