#!/usr/bin/env python3
"""
Обогащение каталога в PostgreSQL (цены, порядок медиа, power lookup) и синхронизация с Meilisearch.

Повторяет логику прежнего export-пайплайна (дедуп по listing key и калькуляторы pricekorea/pricechina),
но upsert в Postgres через общую SQL-логику ingestion.

Опционально: статический дамп `web/public/cars.json` (+ chunks в `web/public/data/`), см. --write-static-json.

Память: дедуп хранит только (cars.id, car_id) на уникальный listing key; полный JSON подгружается
батчами. Порция обработки — --process-batch-size (сборка + цены + upsert).
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
    china_has_source_price,
    china_market_car,
    clear_estimated_price_fields,
    encar_has_list_price,
    encar_reserved_placeholder_price,
)
from catalog_encar_pricing import PRICING_RULES_VERSION, encar_tier_for_pricing_snapshot, sync_pricing_clean_block
from pricechina import CHINA_PRICING_RULES_VERSION, sync_china_pricing_clean_block
from catalog_pg_core import (
    UPSERT_CAR_SQL,
    extract_image_urls,
    get_or_create_brand,
    get_or_create_model,
    row_to_car_fields,
)
from localization.term_localizer import PgTermLocalizer, localize_car_data, localize_china_data
from scraper_pipeline.pg_dsn_resolve import resolve_scraper_postgres_dsn

_BACKEND_DIR = Path(__file__).resolve().parent


def _resolve_repo_root() -> Path:
    """Monorepo: …/backend/ → repo root. Docker WORKDIR=/app: …/app если смонтирован ./infrastructure/meilisearch."""
    backend = _BACKEND_DIR
    env = (os.environ.get("RIDEAUTO_REPO_ROOT") or "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p
    up = backend.parent
    flat = backend / "infrastructure" / "meilisearch" / "sync_meilisearch.py"
    mono = up / "infrastructure" / "meilisearch" / "sync_meilisearch.py"
    # Сначала flat (compose volume ./infrastructure/meilisearch → /app/infrastructure/meilisearch).
    if flat.is_file():
        return backend
    if mono.is_file():
        return up
    # Не возвращаем parent(/app)==«/» — иначе ищется /infrastructure (старый баг в Docker).
    return backend


_REPO_ROOT = _resolve_repo_root()
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


def _coerce_pg_jsonb_dict(value: Any) -> Optional[dict]:
    """Разбор JSONB/JSON в dict для ячеек cars.data (и аналогов)."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, memoryview)):
        try:
            value = json.loads(bytes(value).decode("utf-8"))
        except Exception:
            return None
    elif isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _dsn_from_config(config: dict) -> str:
    return resolve_scraper_postgres_dsn(config)


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
        print(
            f"Warning: meilisearch sync script not found: {sync_py}\n"
            "  Ожидается volume в compose: ./infrastructure/meilisearch:/app/infrastructure/meilisearch\n"
            "  и свежий код в образе: docker compose build api && docker compose up -d api\n"
            "  (git pull на хосте сам по себе не обновляет Python внутри контейнера.)",
            file=sys.stderr,
        )
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
        if r.returncode == 2:
            print(
                "Hint: при WRA_MEILI_PREFLIGHT_GATE документы в индекс не пишутся, если не прошли пороги "
                "(например price_coverage). Пустой Meili → пустой каталог в поиске. "
                "Временно: WRA_MEILI_PREFLIGHT_GATE=false при запуске синка или снизьте пороги в sync_meilisearch.",
                file=sys.stderr,
            )


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
    process_batch_size: int = 500,
    max_static_listings: int = 25_000,
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

    try:
        from power_from_external import invalidate_hp_catalog_cache

        invalidate_hp_catalog_cache()
    except ImportError:
        pass

    conn = psycopg2.connect(dsn)
    localizer = PgTermLocalizer(dsn)
    localizer.open()
    brand_cache: Dict[str, int] = {}
    model_cache: Dict[Tuple[int, str], int] = {}

    static_sink: Optional[List[dict]] = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, car_id, data, raw, source_internal_id, needs_pricing_recompute
                FROM cars
                ORDER BY id ASC
                """
            )
            # Только id победившей строки: не копируем JSON всех карточек в RAM (иначе OOM на ~300k+).
            best: Dict[str, Tuple[int, str]] = {}
            while True:
                chunk = cur.fetchmany(500)
                if not chunk:
                    break
                for row in chunk:
                    pg_id, car_id, data, _raw, _source_internal_id, _needs_rq = row
                    data_dict = _coerce_pg_jsonb_dict(data)
                    if data_dict is None:
                        continue
                    lk = listing_key_for_export(str(car_id), data_dict)
                    prev = best.get(lk)
                    if prev is None or int(pg_id) > int(prev[0]):
                        best[lk] = (int(pg_id), str(car_id))

        ordered: List[Tuple[int, str]] = sorted(best.values(), key=lambda x: x[0])
        del best
        n_total = len(ordered)
        print(f"Postgres catalog: unique listings={n_total} (from rows, deduped)", file=sys.stderr)

        proc_batch = max(1, int(process_batch_size))
        print(
            f"Loading + processing batches of {proc_batch} rows (fetch JSONB by id, then prices + upsert).",
            file=sys.stderr,
        )

        if write_static_json:
            if max_static_listings > 0 and n_total > max_static_listings:
                print(
                    f"Warning: --write-static-json skipped: {n_total} listings > max_static_listings={max_static_listings} "
                    f"(would duplicate full catalog in RAM). Use --max-static-listings 0 to force (OOM risk) or export separately.",
                    file=sys.stderr,
                )
            else:
                static_sink = []

        calc_korea = calc_china = None
        if not no_prices:
            try:
                from market_pricing_shared import PricingFxRates
                from pricechina import PriceCalculatorChina
                from pricekorea import PriceCalculatorKorea

                cfg_path = next(
                    (p for p in (_BACKEND_DIR / "config.json", _REPO_ROOT / "config.json") if p.is_file()),
                    _BACKEND_DIR / "config.json",
                )
                fx = PricingFxRates(config_path=str(cfg_path))
                calc_korea = PriceCalculatorKorea(fx=fx)
                calc_china = PriceCalculatorChina(fx=fx)
            except ImportError as e:
                print(f"Warning: price module not found, skip prices: {e}", file=sys.stderr)

        price_ok = price_failed = price_ok_china = price_skipped_china = 0
        price_skipped_no_list = price_skipped_encar_on_request = 0
        price_ok_land_only_encar = 0
        global_idx = 0

        def _apply_prices_to_batch(cars_out: List[dict]) -> None:
            nonlocal price_ok, price_failed, price_ok_china, price_skipped_china
            nonlocal price_skipped_no_list, price_skipped_encar_on_request, price_ok_land_only_encar, global_idx
            if no_prices or not cars_out or calc_korea is None or calc_china is None:
                return
            for car in cars_out:
                i = global_idx
                global_idx += 1
                data = car.get("data")
                if data is None:
                    data = car
                if not isinstance(data, dict):
                    continue

                if _uses_china_pipeline_pricing(car):
                    if not china_has_source_price(data):
                        price_skipped_china += 1
                        data["price_on_request"] = True
                        data["pricing_tier"] = "price_on_request"
                        clear_estimated_price_fields(data)
                        data.pop("price_calc_failed", None)
                        sync_china_pricing_clean_block(data)
                    else:
                        try:
                            calc_china.update_china_car_with_prices(data)
                            data.pop("price_on_request", None)
                            data.pop("price_calc_failed", None)
                            data["pricing_tier"] = "full_customs"
                            sync_china_pricing_clean_block(data)
                            price_ok += 1
                            price_ok_china += 1
                        except Exception as e:
                            price_failed += 1
                            if i == 0:
                                print(f"Warning: china price calc failed for first car: {e}", file=sys.stderr)
                            data["price_on_request"] = True
                            data["pricing_tier"] = "price_on_request"
                            data["price_calc_failed"] = True
                            clear_estimated_price_fields(data)
                            sync_china_pricing_clean_block(data)
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

                tier = encar_tier_for_pricing_snapshot(data)

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

        pending = 0
        for batch_lo in range(0, n_total, proc_batch):
            batch_hi = min(batch_lo + proc_batch, n_total)
            id_slice = ordered[batch_lo:batch_hi]
            batch_pg_ids = [p[0] for p in id_slice]
            rows_by_pg: Dict[int, Tuple[str, dict, Any, Any, bool]] = {}
            with conn.cursor() as bcur:
                bcur.execute(
                    """
                    SELECT id, car_id, data, raw, source_internal_id, needs_pricing_recompute
                    FROM cars
                    WHERE id = ANY(%s)
                    """,
                    (batch_pg_ids,),
                )
                for brow in bcur.fetchall():
                    b_pg_id, b_car_id, b_data, b_raw, b_src_id, b_needs = brow
                    b_payload = _coerce_pg_jsonb_dict(b_data)
                    if b_payload is None:
                        continue
                    rows_by_pg[int(b_pg_id)] = (
                        str(b_car_id),
                        b_payload,
                        b_raw,
                        b_src_id,
                        bool(b_needs),
                    )

            slice_tuples: List[Tuple[int, str, dict, Any, Any, bool]] = []
            for pg_id, _car_id_hint in id_slice:
                rec = rows_by_pg.get(int(pg_id))
                if rec is None:
                    print(f"Warning: batch fetch missed cars.id={pg_id}, skip", file=sys.stderr)
                    continue
                car_id, payload, raw, source_internal_id, nr_flag = rec
                slice_tuples.append((int(pg_id), car_id, payload, raw, source_internal_id, nr_flag))

            cars_out: List[dict] = []
            for _pg_id, car_id, payload, _raw, _sql_id, nr_flag in slice_tuples:
                car = dict(payload)
                car["id"] = car_id
                car["_pg_needs_pricing_recompute"] = bool(nr_flag)
                if isinstance(car.get("data"), dict):
                    car["data"]["id"] = str(car_id)
                    normalize_car_media_fields(car)
                    if not no_power_lookup and not _uses_china_pipeline_pricing(car):
                        fill_power_from_external(car["data"])
                    if _uses_china_pipeline_pricing(car):
                        localize_china_data(car["data"], localizer)
                    else:
                        localize_car_data(car["data"], localizer)
                        if not no_power_lookup:
                            fill_power_from_external(car["data"])
                cars_out.append(car)

            _apply_prices_to_batch(cars_out)

            meta_by_car_id = {str(t[1]): (t[3], t[4]) for t in slice_tuples}
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
                    if isinstance(car, dict):
                        car.pop("_raw", None)
                        inner = car.get("data")
                        if isinstance(inner, dict):
                            inner.pop("_raw", None)
                    if not no_prices:
                        car["_catalog_needs_pricing_recompute"] = False
                    else:
                        car["_catalog_needs_pricing_recompute"] = bool(car.get("_pg_needs_pricing_recompute", False))
                    fields = row_to_car_fields(
                        str(cid),
                        car,
                        source_internal_id=source_internal_id if source_internal_id is not None else None,
                    )
                    car.pop("_catalog_needs_pricing_recompute", None)
                    car.pop("_pg_needs_pricing_recompute", None)
                    bid = get_or_create_brand(cur, brand_cache, fields["mark"])
                    mid = get_or_create_model(cur, model_cache, bid, fields["model"]) if bid else None
                    params = {
                        **fields,
                        "brand_id": bid,
                        "model_id": mid,
                        "data": psycopg2.extras.Json(_tree_for_pg_jsonb(car)),
                        "raw": raw_adapted,
                        "created_at": None,
                        "sync_clear_pricing_recompute_queue": not no_prices,
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
                    pending = 0

            if static_sink is not None:
                static_sink.extend(cars_out)

            del cars_out
            del slice_tuples
            del meta_by_car_id
            del rows_by_pg
            del id_slice

            bidx = batch_lo // proc_batch
            if (bidx + 1) % 20 == 0 or batch_hi >= n_total:
                print(f"  … processed {batch_hi}/{n_total} listings", file=sys.stderr)

        if not no_prices and (calc_korea is not None or calc_china is not None):
            print(
                f"Price calc summary: ok={price_ok} failed={price_failed} "
                f"ok_china={price_ok_china} skipped_china_no_price={price_skipped_china} "
                f"skipped_no_list_price={price_skipped_no_list} "
                f"skipped_encar_on_request={price_skipped_encar_on_request} "
                f"ok_encar_land_only_excl_rf_customs={price_ok_land_only_encar} "
                f"total={n_total}",
                file=sys.stderr,
            )
        try:
            with conn.cursor() as mcur:
                mcur.execute("SELECT COUNT(*) FROM cars WHERE needs_pricing_recompute IS TRUE")
                n_pricing_queued = int(mcur.fetchone()[0])
                mcur.execute(
                    """
                    SELECT COUNT(*) FROM cars
                    WHERE (source IS NULL OR lower(trim(source)) = 'encar')
                      AND (car_id IS NULL OR car_id NOT LIKE 'che168-%%')
                      AND COALESCE(data->'pricing_clean'->>'pricing_rules_version', '') <> %s
                      AND (data ? 'price_won' AND NULLIF((data->>'price_won')::text, '') IS NOT NULL
                           AND (data->>'price_won')::numeric > 0)
                    """,
                    (PRICING_RULES_VERSION,),
                )
                n_encar_rules_mismatch = int(mcur.fetchone()[0])
                mcur.execute(
                    """
                    SELECT COUNT(*) FROM cars
                    WHERE lower(trim(source)) = 'che168'
                      AND COALESCE(che168_listing_sold, false) = false
                      AND COALESCE(data->'pricing_clean'->>'pricing_rules_version', '') <> %s
                      AND NULLIF((data->>'price_cny')::text, '') IS NOT NULL
                      AND (data->>'price_cny')::numeric > 0
                    """,
                    (CHINA_PRICING_RULES_VERSION,),
                )
                n_china_rules_mismatch = int(mcur.fetchone()[0])
            print(
                f"Pricing observability: needs_pricing_recompute={n_pricing_queued} "
                f"encar_rows_old_pricing_rules_version≈{n_encar_rules_mismatch} (current={PRICING_RULES_VERSION}) "
                f"che168_rows_old_china_pricing_rules_version≈{n_china_rules_mismatch} (current={CHINA_PRICING_RULES_VERSION})",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"Warning: pricing observability query failed: {e}", file=sys.stderr)
        print(f"Postgres upsert + images: {n_total} listings", file=sys.stderr)
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

    if write_static_json and static_sink is not None:
        _write_static_catalog(
            static_sink,
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
        "--process-batch-size",
        type=int,
        default=500,
        help="Сколько объявлений одновременно: сборка + расчёт цен + upsert (снижает пик RAM; дедуп по-прежнему держит весь каталог в памяти).",
    )
    p.add_argument(
        "--max-static-listings",
        type=int,
        default=25_000,
        help="При --write-static-json не копировать весь каталог в RAM, если объявлений больше этого числа. 0 = без лимита (риск OOM на больших БД).",
    )
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
        dsn = resolve_scraper_postgres_dsn({})
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
        process_batch_size=max(1, args.process_batch_size),
        max_static_listings=max(0, args.max_static_listings),
        write_static_json=static_export,
        static_gzip=args.static_gzip,
        static_chunk_size=max(0, args.static_chunk_size),
        run_meili=not args.no_meilisearch,
        run_learn=args.learn_engine_map
        or os.environ.get("AUTO_LEARN_ENGINE_MAP", "").strip().lower() in ("1", "true", "yes", "on"),
    )


if __name__ == "__main__":
    raise SystemExit(main())

