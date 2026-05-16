#!/usr/bin/env python3
"""
Пересчёт price_cny для Che168 из che168_price_raw (новые эвристики parser.py).

Обновляет cars.data, ставит needs_pricing_recompute=TRUE.
После прогона: postgres_catalog_sync (цены ₽, Meili).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote, urlsplit, urlunsplit

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
    return (os.environ.get("DATABASE_URL") or os.environ.get("RIDEAUTO_PG_CHECKPOINT_DSN") or "").strip()


def _dsn_for_host_outside_compose(dsn: str) -> str:
    s = (dsn or "").strip()
    if not s:
        return s
    p = urlsplit(s)
    if not p.hostname or str(p.hostname).lower() != "postgres":
        return s
    port = p.port if p.port is not None else 5432
    auth = ""
    if p.username:
        uq = quote(p.username, safe="")
        if p.password is not None:
            uq += ":" + quote(p.password, safe="")
        auth = uq + "@"
    netloc = f"{auth}127.0.0.1:{port}"
    return urlunsplit((p.scheme, netloc, p.path, p.query, p.fragment))


def _inner_data(data: Dict[str, Any]) -> Dict[str, Any]:
    inner = data.get("data")
    return inner if isinstance(inner, dict) else data


def _json_path_sql(field: str) -> str:
    """cars.data в Postgres: поля карточки в data->'data' (parser envelope)."""
    return f"COALESCE(data->'data'->>'{field}', data->>'{field}')"


def _price_context(inner: Dict[str, Any]) -> str:
    parts: List[str] = []
    for k in ("title", "subtitle", "name", "che168_displacement_label"):
        v = inner.get(k)
        if v is not None and str(v).strip():
            parts.append(str(v).strip())
    return " ".join(parts)


def _reprice_inner(inner: Dict[str, Any], *, assume_wan_yuan: bool) -> Tuple[Dict[str, Any], bool]:
    from scraper_pipeline.che168.parser import normalize_price_cny_detailed

    raw_price = inner.get("che168_price_raw")
    if raw_price in (None, ""):
        raw_price = inner.get("price")
    price_cny, meta = normalize_price_cny_detailed(
        raw_price,
        assume_wan_yuan=assume_wan_yuan,
        price_context=_price_context(inner),
    )
    old_cny = inner.get("price_cny")
    old_rule = inner.get("che168_price_cny_rule")
    new_rule = meta.get("che168_price_cny_rule")
    changed = old_cny != price_cny or old_rule != new_rule
    if not changed:
        return inner, False
    if price_cny is not None:
        inner["price_cny"] = price_cny
    else:
        inner.pop("price_cny", None)
    inner.update(meta)
    inner["price_on_request"] = bool(price_cny is None or float(price_cny) <= 0)
    inner.pop("my_price", None)
    inner.pop("price_rub_estimate", None)
    inner.pop("vehicle_sum_rub", None)
    inner.pop("pricing_clean", None)
    return inner, True


def main() -> int:
    from scraper_pipeline.che168.parser import normalize_price_cny_detailed  # noqa: F401

    p = argparse.ArgumentParser(description="Backfill Che168 price_cny from che168_price_raw")
    p.add_argument("--config", default="che168_scraper.yaml")
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--limit", type=int, default=0, help="0 = all rows")
    p.add_argument("--apply", action="store_true")
    p.add_argument(
        "--only-legacy-raw",
        action="store_true",
        help="Only rows with che168_price_cny_rule=raw_cny_integer and 1000<=price_cny<100000",
    )
    p.add_argument("--assume-wan-yuan", action="store_true")
    args = p.parse_args()

    dsn = _dsn_for_host_outside_compose(_dsn(Path(args.config).expanduser().resolve()))
    if not dsn:
        print("DATABASE_URL / storage.postgres.dsn required", file=sys.stderr)
        return 2

    import psycopg2
    import psycopg2.extras

    where = "lower(trim(source)) = 'che168'"
    if args.only_legacy_raw:
        rule = _json_path_sql("che168_price_cny_rule")
        price = _json_path_sql("price_cny")
        where += (
            f" AND {rule} = 'raw_cny_integer'"
            f" AND NULLIF({price}, '') IS NOT NULL"
            f" AND ({price})::numeric >= 1000"
            f" AND ({price})::numeric < 100000"
        )

    count_sql = f"SELECT COUNT(*) FROM cars WHERE {where}"
    id_sql = f"""
        SELECT id, car_id, data
        FROM cars
        WHERE {where}
        ORDER BY id ASC
    """
    if args.limit and args.limit > 0:
        id_sql += f" LIMIT {int(args.limit)}"

    stats = {
        "scanned": 0,
        "changed": 0,
        "updated": 0,
        "skipped_no_raw": 0,
        "apply": bool(args.apply),
    }
    t0 = time.time()

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql)
            total = int(cur.fetchone()[0])
        print(f"che168_price_backfill: candidates={total} apply={args.apply}", flush=True)

        last_id = 0
        processed = 0
        while True:
            if args.limit and processed >= args.limit:
                break
            batch_lim = args.batch_size
            if args.limit:
                batch_lim = min(batch_lim, args.limit - processed)

            q = f"""
                SELECT id, car_id, data
                FROM cars
                WHERE {where} AND id > %s
                ORDER BY id ASC
                LIMIT %s
            """
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (last_id, batch_lim))
                rows = cur.fetchall()
            if not rows:
                break

            updates: List[Tuple[str, int]] = []
            for row in rows:
                stats["scanned"] += 1
                rid = int(row["id"])
                last_id = rid
                data = row.get("data")
                if not isinstance(data, dict):
                    continue
                inner = _inner_data(data)
                if inner.get("che168_price_raw") in (None, "") and inner.get("price") in (None, ""):
                    stats["skipped_no_raw"] += 1
                    continue
                new_inner, changed = _reprice_inner(
                    dict(inner),
                    assume_wan_yuan=bool(args.assume_wan_yuan),
                )
                if not changed:
                    continue
                stats["changed"] += 1
                if isinstance(data.get("data"), dict):
                    out = dict(data)
                    out["data"] = new_inner
                else:
                    out = new_inner
                updates.append((json.dumps(out, ensure_ascii=False), rid))

            if args.apply and updates:
                with conn.cursor() as cur:
                    psycopg2.extras.execute_batch(
                        cur,
                        """
                        UPDATE cars
                        SET data = %s::jsonb,
                            needs_pricing_recompute = TRUE,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        updates,
                        page_size=100,
                    )
                conn.commit()
                stats["updated"] += len(updates)
            elif updates:
                stats["updated"] += len(updates)

            processed += len(rows)
            elapsed = time.time() - t0
            rate = stats["scanned"] / elapsed if elapsed > 0 else 0
            print(
                f"  progress scanned={stats['scanned']}/{total} "
                f"changed={stats['changed']} updated={stats['updated']} "
                f"rate={rate:.1f}/s",
                flush=True,
            )

    stats["elapsed_sec"] = round(time.time() - t0, 1)
    print(json.dumps(stats, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
