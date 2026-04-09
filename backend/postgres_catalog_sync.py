#!/usr/bin/env python3
"""
Обогащение каталога в PostgreSQL (цены, порядок медиа, power lookup) и синхронизация с Meilisearch.

Повторяет логику прежнего export-пайплайна (дедуп по listing key и PriceCalculator),
но upsert в Postgres через общую SQL-логику ingestion.

Опционально: статический дамп `web/public/cars.json` (+ chunks в `web/public/data/`), см. --write-static-json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from catalog_pg_core import (
    UPSERT_CAR_SQL,
    extract_image_urls,
    get_or_create_brand,
    get_or_create_model,
    row_to_car_fields,
)
from localization.term_localizer import PgTermLocalizer, localize_car_data

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def _dsn_from_config(config: dict) -> str:
    storage_cfg = config.get("storage", {}) or {}
    dsn = (storage_cfg.get("postgres") or {}).get("dsn") or ""
    dsn = str(dsn).strip()
    if dsn:
        return dsn
    return (os.environ.get("DATABASE_URL") or "").strip()


def _load_yaml_config(path: Path) -> dict:
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _maybe_run_meili(dsn: str) -> None:
    if os.environ.get("SKIP_MEILISEARCH_SYNC", "").strip().lower() in ("1", "true", "yes", "on"):
        print("Meilisearch sync skipped (SKIP_MEILISEARCH_SYNC)", file=sys.stderr)
        return
    url = (os.environ.get("WRA_MEILISEARCH_URL") or "").strip()
    if not url:
        print("Meilisearch sync skipped (WRA_MEILISEARCH_URL empty)", file=sys.stderr)
        return
    key = (
        os.environ.get("WRA_MEILISEARCH_KEY")
        or os.environ.get("MEILI_MASTER_KEY")
        or ""
    ).strip()
    index = (os.environ.get("WRA_MEILISEARCH_INDEX") or "cars").strip()
    sync_py = _REPO_ROOT / "infrastructure" / "meilisearch" / "sync_meilisearch.py"
    settings_json = _REPO_ROOT / "infrastructure" / "meilisearch" / "index_settings.json"
    if not sync_py.is_file():
        print(f"Warning: meilisearch sync script not found: {sync_py}", file=sys.stderr)
        return
    if not settings_json.is_file():
        print(f"Warning: meilisearch settings not found: {settings_json}", file=sys.stderr)
        return
    cmd = [
        sys.executable,
        str(sync_py),
        "--pg-dsn",
        dsn,
        "--meili-url",
        url,
        "--index-name",
        index,
        "--settings",
        str(settings_json),
    ]
    if key:
        cmd.extend(["--meili-key", key])
    print(f"Running Meilisearch sync: {sync_py.name} …", file=sys.stderr)
    r = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    if r.returncode != 0:
        print(f"Warning: meilisearch sync exited {r.returncode}", file=sys.stderr)


def _maybe_learn_engine_map() -> None:
    learn = _BACKEND_DIR / "scripts" / "auto_learn_engine_map.py"
    if not learn.is_file():
        return
    r = subprocess.run(
        [sys.executable, str(learn), "--repo", str(_REPO_ROOT)],
        cwd=str(_REPO_ROOT),
    )
    if r.returncode != 0:
        print(f"Warning: auto_learn_engine_map.py exited {r.returncode}", file=sys.stderr)


def _write_static_catalog(
    cars: List[dict],
    *,
    gzip_enabled: bool,
    chunk_size: int,
) -> None:
    from catalog_export_utils import iter_chunks, write_json_atomic

    out_path = _REPO_ROOT / "web" / "public" / "cars.json"
    out = {"result": cars, "meta": {"page": 1, "next_page": 2, "limit": len(cars)}}
    write_json_atomic(out_path, out, gzip_enabled=gzip_enabled)
    print(f"Static JSON: {out_path} ({len(cars)} cars)", file=sys.stderr)
    if chunk_size > 0:
        chunk_dir = _REPO_ROOT / "web" / "public" / "data" / "chunks"
        index_path = _REPO_ROOT / "web" / "public" / "data" / "cars.index.json"
        files = []
        for page_num, chunk in iter_chunks(cars, chunk_size):
            name = f"cars_{page_num:05d}.json"
            chunk_payload = {
                "result": chunk,
                "meta": {
                    "page": page_num,
                    "limit": len(chunk),
                    "total": len(cars),
                    "chunk_size": chunk_size,
                },
            }
            chunk_path = chunk_dir / name
            write_json_atomic(chunk_path, chunk_payload, gzip_enabled=gzip_enabled)
            files.append(
                {
                    "page": page_num,
                    "file": str(Path("data") / "chunks" / name).replace("\\", "/"),
                    "count": len(chunk),
                }
            )
        index_payload = {
            "total": len(cars),
            "chunk_size": chunk_size,
            "pages": len(files),
            "files": files,
        }
        write_json_atomic(index_path, index_payload, gzip_enabled=gzip_enabled)
        print(f"Chunks: {len(files)} files → {chunk_dir}", file=sys.stderr)


def _uses_china_pipeline_pricing(car: dict) -> bool:
    """Dongchedi уже кладёт my_price (RUB) в data; корейский PriceCalculator их портит."""
    d = car.get("data") if isinstance(car.get("data"), dict) else None
    if d and str(d.get("source") or "").strip().lower() == "dongchedi":
        return True
    return str(car.get("id") or "").lower().startswith("dongchedi-")


def run_sync(
    dsn: str,
    *,
    no_prices: bool = False,
    no_power_lookup: bool = False,
    batch_commit: int = 200,
    write_static_json: bool = False,
    static_gzip: bool = False,
    static_chunk_size: int = 0,
    run_meili: bool = True,
    run_learn: bool = False,
) -> int:
    import psycopg2.extras

    from catalog_export_utils import (
        fill_power_from_external,
        listing_key_for_export,
        normalize_car_media_fields,
    )

    import psycopg2

    conn = psycopg2.connect(dsn)
    localizer = PgTermLocalizer(dsn)
    localizer.open()
    brand_cache: Dict[str, int] = {}
    model_cache: Dict[Tuple[int, str], int] = {}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, car_id, data, raw, source_internal_id
                FROM cars
                ORDER BY id ASC
                """
            )
            best: Dict[str, Tuple[int, str, Any, Any, Any]] = {}
            while True:
                chunk = cur.fetchmany(500)
                if not chunk:
                    break
                for row in chunk:
                    pg_id, car_id, data, raw, source_internal_id = row
                    if data is None:
                        continue
                    if isinstance(data, (bytes, memoryview)):
                        try:
                            data = json.loads(bytes(data).decode("utf-8"))
                        except Exception:
                            continue
                    elif isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                    if not isinstance(data, dict):
                        continue
                    lk = listing_key_for_export(str(car_id), data)
                    prev = best.get(lk)
                    if prev is None or int(pg_id) > int(prev[0]):
                        best[lk] = (int(pg_id), str(car_id), data, raw, source_internal_id)

        ordered: List[Tuple[int, str, dict, Any, Any]] = sorted(
            (
                (int(t[0]), str(t[1]), t[2], t[3], t[4])
                for t in best.values()
            ),
            key=lambda x: x[0],
        )
        print(f"Postgres catalog: unique listings={len(ordered)} (from rows, deduped)", file=sys.stderr)

        cars_out: List[dict] = []
        for _pg_id, car_id, payload, _raw, _sql_id in ordered:
            car = dict(payload)
            car["id"] = car_id
            if isinstance(car.get("data"), dict):
                car["data"]["id"] = str(car_id)
                normalize_car_media_fields(car)
                if not no_power_lookup and not _uses_china_pipeline_pricing(car):
                    fill_power_from_external(car["data"])
                localize_car_data(car["data"], localizer)
            cars_out.append(car)

        if not no_prices and cars_out:
            try:
                from price import PriceCalculator

                cfg_path = next(
                    (p for p in (_BACKEND_DIR / "config.json", _REPO_ROOT / "config.json") if p.is_file()),
                    _BACKEND_DIR / "config.json",
                )
                calc = PriceCalculator(config_path=str(cfg_path))
                price_ok = price_failed = price_skipped = 0
                for i, car in enumerate(cars_out):
                    if _uses_china_pipeline_pricing(car):
                        price_skipped += 1
                        continue
                    data = car.get("data")
                    if data is None:
                        data = car
                    try:
                        calc.update_car_with_prices(data)
                        if car.get("data") is not data:
                            car["data"] = data
                        if isinstance(data, dict):
                            data.pop("price_calc_failed", None)
                        price_ok += 1
                    except Exception as e:
                        price_failed += 1
                        if i == 0:
                            print(f"Warning: price calc failed for first car: {e}", file=sys.stderr)
                        if isinstance(data, dict):
                            data["price_calc_failed"] = True
                        if car.get("data") is not data:
                            car["data"] = data
                print(
                    f"Price calc summary: ok={price_ok} failed={price_failed} "
                    f"skipped_china={price_skipped} total={len(cars_out)}",
                    file=sys.stderr,
                )
            except ImportError as e:
                print(f"Warning: price module not found, skip prices: {e}", file=sys.stderr)

        meta_by_car_id: Dict[str, Tuple[Any, Any]] = {
            str(t[1]): (t[3], t[4]) for t in ordered
        }
        pending = 0
        with conn.cursor() as cur:
            for car in cars_out:
                cid = car.get("id")
                if not cid:
                    continue
                raw_obj, source_internal_id = meta_by_car_id.get(str(cid), (None, None))
                if isinstance(raw_obj, (bytes, memoryview)):
                    try:
                        raw_obj = json.loads(bytes(raw_obj).decode("utf-8"))
                    except Exception:
                        raw_obj = None
                elif isinstance(raw_obj, str):
                    try:
                        raw_obj = json.loads(raw_obj)
                    except json.JSONDecodeError:
                        raw_obj = {"_raw_text": raw_obj}
                raw_adapted = psycopg2.extras.Json(raw_obj) if isinstance(raw_obj, dict) else None
                fields = row_to_car_fields(
                    str(cid),
                    car,
                    source_internal_id=source_internal_id if source_internal_id is not None else None,
                )
                bid = get_or_create_brand(cur, brand_cache, fields["mark"])
                mid = get_or_create_model(cur, model_cache, bid, fields["model"]) if bid else None
                params = {
                    **fields,
                    "brand_id": bid,
                    "model_id": mid,
                    "data": psycopg2.extras.Json(car),
                    "raw": raw_adapted,
                    "created_at": None,
                }
                cur.execute(UPSERT_CAR_SQL, params)
                row = cur.fetchone()
                if not row:
                    continue
                car_pk = int(row[0])
                urls = extract_image_urls(car)
                cur.execute("DELETE FROM car_images WHERE car_pk = %s", (car_pk,))
                for i, url in enumerate(urls):
                    cur.execute(
                        """
                        INSERT INTO car_images (car_pk, url, sort_order, is_primary)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (car_pk, url) DO UPDATE SET
                            sort_order = EXCLUDED.sort_order,
                            is_primary = EXCLUDED.is_primary
                        """,
                        (car_pk, url, i, i == 0),
                    )
                pending += 1
                if pending >= max(1, batch_commit):
                    conn.commit()
                    pending = 0
            if pending:
                conn.commit()
        print(f"Postgres upsert + images: {len(cars_out)} listings", file=sys.stderr)
    finally:
        try:
            localizer.close()
        except Exception:
            pass
        conn.close()

    print(
        (
            "Localization stats: "
            f"cache_hits={localizer.stats.cache_hits} "
            f"llm_calls={localizer.stats.llm_calls} "
            f"llm_success={localizer.stats.llm_success} "
            f"llm_failed={localizer.stats.llm_failed} "
            f"skipped_budget={localizer.stats.skipped_budget}"
        ),
        file=sys.stderr,
    )

    if write_static_json:
        _write_static_catalog(
            cars_out,
            gzip_enabled=static_gzip,
            chunk_size=max(0, static_chunk_size),
        )

    if run_meili:
        _maybe_run_meili(dsn)
    if run_learn:
        _maybe_learn_engine_map()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Enc richness + upsert PostgreSQL (+ optional Meili / static JSON)")
    p.add_argument("--config", default="", help="scraper_config.yaml (reads storage.postgres.dsn)")
    p.add_argument("--dsn", default="", help="Override PostgreSQL DSN")
    p.add_argument("--no-prices", action="store_true")
    p.add_argument("--no-power-lookup", action="store_true")
    p.add_argument("--batch-commit", type=int, default=200)
    p.add_argument(
        "--write-static-json",
        action="store_true",
        help="Also write web/public/cars.json (and optional chunks under web/public/data/)",
    )
    p.add_argument("--static-gzip", action="store_true")
    p.add_argument("--static-chunk-size", type=int, default=0)
    p.add_argument("--no-meilisearch", action="store_true")
    p.add_argument("--learn-engine-map", action="store_true")
    args = p.parse_args()

    dsn = (args.dsn or "").strip()
    if not dsn and args.config:
        cfg_path = Path(args.config).expanduser()
        if not cfg_path.is_file():
            print(f"Config not found: {cfg_path}", file=sys.stderr)
            return 2
        cfg = _load_yaml_config(cfg_path)
        dsn = _dsn_from_config(cfg)
    if not dsn:
        print("PostgreSQL DSN required (--dsn or config storage.postgres.dsn / DATABASE_URL)", file=sys.stderr)
        return 2

    static_export = args.write_static_json or os.environ.get("WRITE_STATIC_CATALOG", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    return run_sync(
        dsn,
        no_prices=args.no_prices,
        no_power_lookup=args.no_power_lookup,
        batch_commit=max(1, args.batch_commit),
        write_static_json=static_export,
        static_gzip=args.static_gzip,
        static_chunk_size=max(0, args.static_chunk_size),
        run_meili=not args.no_meilisearch,
        run_learn=args.learn_engine_map
        or os.environ.get("AUTO_LEARN_ENGINE_MAP", "").strip().lower() in ("1", "true", "yes", "on"),
    )


if __name__ == "__main__":
    raise SystemExit(main())

