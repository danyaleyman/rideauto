#!/usr/bin/env python3
"""
Обогащение каталога в PostgreSQL (цены, порядок медиа, power lookup) и синхронизация с Meilisearch.

Повторяет логику прежнего export-пайплайна (дедуп по listing key и калькуляторы pricekorea/pricechina),
но upsert в Postgres через общую SQL-логику ingestion.

Опционально: статический дамп `web/public/cars.json` (+ chunks в `web/public/data/`), см. --write-static-json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from catalog_listing_price import (
    china_market_car,
    clear_estimated_price_fields,
    dongchedi_has_buyer_price,
    dongchedi_has_source_price,
    encar_has_list_price,
    encar_reserved_placeholder_price,
)
from catalog_encar_pricing import encar_catalog_pricing_tier, sync_pricing_clean_block
from catalog_pg_core import (
    UPSERT_CAR_SQL,
    extract_image_urls,
    get_or_create_brand,
    get_or_create_model,
    row_to_car_fields,
)
from localization.term_localizer import PgTermLocalizer, localize_car_data, localize_china_data

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def _tree_for_pg_jsonb(value: Any) -> Any:
    """
    Build a strictly JSON-safe tree for psycopg2.extras.Json(): copy dict/list, break Python-only
    cycles (stdlib encoder raises Circular reference detected), coerce odd scalars.

    Mirrors what eventually goes to Postgres JSONB; duplication of shared subgraphs is acceptable.
    """
    stack: set[int] = set()

    def _walk(x: Any) -> Any:
        if x is None or isinstance(x, bool):
            return x
        if isinstance(x, str):
            return x
        if isinstance(x, (bytes, memoryview)):
            try:
                return bytes(x).decode("utf-8", errors="replace")
            except Exception:
                return str(x)
        if isinstance(x, int):
            return x
        if isinstance(x, float):
            if math.isnan(x) or math.isinf(x):
                return None
            return x
        if isinstance(x, Decimal):
            return format(x, "f")
        if isinstance(x, (datetime, date)):
            try:
                return x.isoformat()
            except Exception:
                return str(x)
        if isinstance(x, dict):
            oid = id(x)
            if oid in stack:
                return None
            stack.add(oid)
            try:
                out: Dict[str, Any] = {}
                for k, v in x.items():
                    sk = k if isinstance(k, str) else str(k)
                    out[sk] = _walk(v)
                return out
            finally:
                stack.discard(oid)
        if isinstance(x, (list, tuple)):
            oid = id(x)
            if oid in stack:
                return None
            stack.add(oid)
            try:
                return [_walk(v) for v in x]
            finally:
                stack.discard(oid)
        return str(x)

    return _walk(value)


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
    recreate = (os.environ.get("WRA_MEILI_RECREATE_INDEX_ON_SYNC") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
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
    if recreate:
        cmd.append("--recreate-index")
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


def _car_inner_data(car: dict) -> Optional[dict]:
    d = car.get("data")
    return d if isinstance(d, dict) else None


def _uses_china_pipeline_pricing(car: dict) -> bool:
    """Китайский рынок: не трогаем корейским калькулятором и локализацией терминов."""
    return china_market_car(str(car.get("id") or ""), _car_inner_data(car))


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
        def _parse_positive_int(value: Any) -> Optional[int]:
            if value is None or value == "":
                return None
            try:
                if isinstance(value, str):
                    digits = "".join(ch for ch in value if ch.isdigit())
                    if not digits:
                        return None
                    iv = int(digits)
                else:
                    iv = int(float(value))
                return iv if iv > 0 else None
            except (TypeError, ValueError):
                return None

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
                if _uses_china_pipeline_pricing(car):
                    localize_china_data(car["data"], localizer)
                else:
                    localize_car_data(car["data"], localizer)
                    # HP lookup runs again after EN/RU normalization: engine_map tends to match English marks
                    # better than Korean-only strings passed on the first pass (before localize).
                    if not no_power_lookup:
                        fill_power_from_external(car["data"])
            cars_out.append(car)

        if not no_prices and cars_out:
            try:
                from market_pricing_shared import PricingFxRates, classify_fuel, parse_power_hp
                from pricechina import PriceCalculatorChina
                from pricekorea import PriceCalculatorKorea

                cfg_path = next(
                    (p for p in (_BACKEND_DIR / "config.json", _REPO_ROOT / "config.json") if p.is_file()),
                    _BACKEND_DIR / "config.json",
                )
                fx = PricingFxRates(config_path=str(cfg_path))
                calc_korea = PriceCalculatorKorea(fx=fx)
                calc_china = PriceCalculatorChina(fx=fx)
                price_ok = price_failed = price_ok_china = price_skipped_china = 0
                price_skipped_no_list = price_skipped_encar_on_request = 0
                price_ok_land_only_encar = 0
                for i, car in enumerate(cars_out):
                    data = car.get("data")
                    if data is None:
                        data = car
                    if not isinstance(data, dict):
                        continue

                    if _uses_china_pipeline_pricing(car):
                        if not dongchedi_has_source_price(data):
                            price_skipped_china += 1
                            data["price_on_request"] = True
                            clear_estimated_price_fields(data)
                            data.pop("price_calc_failed", None)
                        else:
                            try:
                                calc_china.update_china_car_with_prices(data)
                                data.pop("price_on_request", None)
                                data.pop("price_calc_failed", None)
                                price_ok += 1
                                price_ok_china += 1
                            except Exception as e:
                                price_failed += 1
                                if i == 0:
                                    print(f"Warning: china price calc failed for first car: {e}", file=sys.stderr)
                                data["price_calc_failed"] = True
                        if car.get("data") is not data:
                            car["data"] = data
                        continue

                    if not encar_has_list_price(data):
                        price_skipped_no_list += 1
                        data["price_on_request"] = True
                        if encar_reserved_placeholder_price(data):
                            data["encar_listing_reserved"] = True
                        else:
                            data.pop("encar_listing_reserved", None)
                        clear_estimated_price_fields(data)
                        if car.get("data") is not data:
                            car["data"] = data
                        continue

                    fuel_kind = classify_fuel(data)
                    hp_raw = parse_power_hp(data)
                    hp_ok = isinstance(hp_raw, (int, float)) and float(hp_raw) > 0
                    cc_val = _parse_positive_int(
                        data.get("displacement")
                        or data.get("displacement_cc")
                        or data.get("engine_volume")
                    )
                    cc_ok = cc_val is not None
                    tier = encar_catalog_pricing_tier(fuel_kind=str(fuel_kind), hp_ok=hp_ok, cc_ok=cc_ok)

                    data.pop("catalog_price_hp_unknown", None)

                    if tier == "price_on_request":
                        price_skipped_encar_on_request += 1
                        data["pricing_tier"] = tier
                        data["price_on_request"] = True
                        clear_estimated_price_fields(data)
                        sync_pricing_clean_block(data)
                        if car.get("data") is not data:
                            car["data"] = data
                        continue

                    data.pop("price_on_request", None)
                    try:
                        if tier == "full_customs":
                            calc_korea.update_car_with_prices(data)
                        elif tier == "korea_land_only":
                            calc_korea.update_car_with_prices_land_only(data)
                            price_ok_land_only_encar += 1
                        else:
                            raise RuntimeError(f"unexpected encar tier: {tier!r}")
                        data["pricing_tier"] = tier
                        sync_pricing_clean_block(data)
                        if car.get("data") is not data:
                            car["data"] = data
                        if isinstance(data, dict):
                            data.pop("price_calc_failed", None)
                        price_ok += 1
                    except Exception as e:
                        price_failed += 1
                        if isinstance(data, dict):
                            clear_estimated_price_fields(data)
                            data["pricing_tier"] = "price_on_request"
                            data["price_on_request"] = True
                            sync_pricing_clean_block(data)
                        if i == 0:
                            print(f"Warning: price calc failed for first car: {e}", file=sys.stderr)
                        if isinstance(data, dict):
                            data["price_calc_failed"] = True
                        if car.get("data") is not data:
                            car["data"] = data
                print(
                    f"Price calc summary: ok={price_ok} failed={price_failed} "
                    f"ok_china={price_ok_china} skipped_china_no_price={price_skipped_china} "
                    f"skipped_no_list_price={price_skipped_no_list} "
                    f"skipped_encar_on_request={price_skipped_encar_on_request} "
                    f"ok_encar_land_only_excl_rf_customs={price_ok_land_only_encar} "
                    f"total={len(cars_out)}",
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
                # `car` may embed a full `_raw` tree under the JSONB `data` column (duplicating `cars.raw`)
                # and in edge cases that tree can contain shared/cyclic dict references, which breaks
                # stdlib JSON encoding for psycopg2.extras.Json. Keep raw in `cars.raw` only.
                if isinstance(car, dict):
                    car.pop("_raw", None)
                    inner = car.get("data")
                    if isinstance(inner, dict):
                        inner.pop("_raw", None)
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
                    "data": psycopg2.extras.Json(_tree_for_pg_jsonb(car)),
                    "raw": raw_adapted,
                    "created_at": None,
                }
                cur.execute(UPSERT_CAR_SQL, params)
                row = cur.fetchone()
                if not row:
                    continue
                car_pk = int(row[0])
                d = car.get("data") if isinstance(car.get("data"), dict) else {}
                if isinstance(d, dict) and d.get("encar_listing_sold") is True:
                    cur.execute(
                        """
                        UPDATE cars
                        SET encar_listing_sold = true,
                            encar_listing_checked_at = now()
                        WHERE id = %s
                        """,
                        (car_pk,),
                    )
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

