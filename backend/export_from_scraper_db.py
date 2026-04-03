"""
Export cars from scraper SQLite DB to frontend JSON.

- Full file: cars.json (legacy frontend format).
- Optional chunked export: chunks + index file.
- Optional gzip for better CDN/static delivery.
- Atomic replace for published files (no half-written JSON on readers).
- Writes price-enriched JSON back into SQLite so /api/cars matches cars.json.
- Writes frontend/data/catalog_facets.json (same shape as GET /api/facets with no filters) for fast catalog first paint.
"""
import argparse
import gzip
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
from api_server import _facets_catalog_sync, _sort_encar_image_url_list, _sort_h_images_list_entries


def _fill_power_from_external(data: dict) -> None:
    """Подставить мощность из data/power_lookup.json (марка/модель/год/объём), если в данных пусто."""
    if not isinstance(data, dict):
        return
    if data.get("power") and str(data.get("power", "")).strip():
        return
    try:
        from power_from_external import get_power_for_car

        hp = get_power_for_car(data, record_source=True)
        if hp is not None:
            data["power"] = str(hp)
    except ImportError:
        pass


def _write_json_atomic(path: Path, payload: dict, gzip_enabled: bool = False) -> None:
    """Write JSON then os.replace for atomic visibility to nginx readers."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    if gzip_enabled:
        gz_path = Path(str(path) + ".gz")
        gz_tmp = gz_path.with_name(gz_path.name + ".tmp")
        try:
            with gzip.open(gz_tmp, "wt", encoding="utf-8") as gz:
                json.dump(payload, gz, ensure_ascii=False)
            gz_tmp.replace(gz_path)
        finally:
            if gz_tmp.exists():
                try:
                    gz_tmp.unlink()
                except OSError:
                    pass


def _iter_chunks(items, chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield i // chunk_size + 1, items[i : i + chunk_size]


def _listing_key_for_export(car_id: str, payload: dict) -> str:
    """Как в API: одна карточка на объявление Encar (inner_id), иначе car_id."""
    raw = payload.get("data") if isinstance(payload.get("data"), dict) else None
    d = raw if isinstance(raw, dict) else payload
    inner = str((d or {}).get("inner_id") or "").strip()
    if inner:
        return f"i:{inner}"
    return f"c:{car_id}"


def _normalize_car_media_fields(car: dict) -> None:
    """Порядок кадров как на Encar — превью/thumbnails берут _001, а не случайные 6 URL."""
    data = car.get("data")
    if not isinstance(data, dict):
        return
    raw_im = data.get("images")
    if isinstance(raw_im, str):
        try:
            arr = json.loads(raw_im)
        except Exception:
            arr = None
        if isinstance(arr, list):
            s = _sort_encar_image_url_list([x for x in arr if isinstance(x, str)])
            data["images"] = json.dumps(s, ensure_ascii=False)
    elif isinstance(raw_im, list):
        s = _sort_encar_image_url_list([x for x in raw_im if isinstance(x, str)])
        data["images"] = s
    raw_h = data.get("h_images")
    if isinstance(raw_h, str):
        try:
            arr = json.loads(raw_h)
        except Exception:
            arr = None
        if isinstance(arr, list):
            s = _sort_h_images_list_entries([x for x in arr if isinstance(x, dict)])
            data["h_images"] = json.dumps(s, ensure_ascii=False)
    elif isinstance(raw_h, list):
        s = _sort_h_images_list_entries([x for x in raw_h if isinstance(x, dict)])
        data["h_images"] = s


def _write_catalog_facets_snapshot(db_path: Path, out_path: Path) -> None:
    """Те же фасеты, что GET /api/facets без фильтров — статика для быстрого первого экрана."""
    facets = _facets_catalog_sync(str(db_path.resolve()), {})
    payload = dict(facets)
    payload["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_json_atomic(Path(out_path), payload, gzip_enabled=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="encar_cars.db", help="Scraper SQLite DB path")
    p.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "frontend" / "cars.json"), help="Output JSON path")
    p.add_argument("--chunk-size", type=int, default=0, help="Chunk size for split export (0 = disabled)")
    p.add_argument("--chunk-dir", default=str(Path(__file__).resolve().parent.parent / "frontend" / "data" / "chunks"), help="Chunk output directory")
    p.add_argument("--chunk-index", default=str(Path(__file__).resolve().parent.parent / "frontend" / "data" / "cars.index.json"), help="Chunk index JSON path")
    p.add_argument("--gzip", action="store_true", help="Write .gz variants for exported JSON files")
    p.add_argument("--no-prices", action="store_true", help="Do not calculate prices (no API calls)")
    p.add_argument("--no-power-lookup", action="store_true", help="Do not fill power from power_lookup.json")
    p.add_argument(
        "--no-sqlite-sync",
        action="store_true",
        help="Do not write priced records back into SQLite (catalog API stays without my_price)",
    )
    p.add_argument(
        "--learn-engine-map",
        action="store_true",
        help="После экспорта запустить auto_learn_engine_map.py (обновить engine_map.json по motorType)",
    )
    p.add_argument(
        "--no-facets-snapshot",
        action="store_true",
        help="Не писать frontend/data/catalog_facets.json (снимок фасетов для каталога)",
    )
    args = p.parse_args()

    db_path = Path(args.db).resolve()
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT id, car_id, data_json FROM cars ORDER BY id").fetchall()
        best: dict[str, tuple] = {}
        for row_id, car_id, data_json in rows:
            try:
                payload = json.loads(data_json)
            except Exception:
                continue
            lk = _listing_key_for_export(str(car_id), payload)
            prev = best.get(lk)
            if prev is None or row_id > prev[0]:
                best[lk] = (row_id, car_id, data_json)
        cars = []
        for row_id, car_id, data_json in sorted(best.values(), key=lambda t: t[0]):
            car = json.loads(data_json)
            car["id"] = car_id
            if isinstance(car.get("data"), dict):
                car["data"]["id"] = str(car_id)
                _normalize_car_media_fields(car)
                if not args.no_power_lookup:
                    _fill_power_from_external(car["data"])
            cars.append(car)

        if not args.no_prices and cars:
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                from price import PriceCalculator

                _bd = Path(__file__).resolve().parent
                _cfg = next(
                    (p for p in (_bd / "config.json", _bd.parent / "config.json") if p.is_file()),
                    _bd / "config.json",
                )
                calc = PriceCalculator(config_path=str(_cfg))
                price_ok = 0
                price_failed = 0
                failed_examples = []
                for i, car in enumerate(cars):
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
                        if len(failed_examples) < 5:
                            car_ref = car.get("id") or (data.get("id") if isinstance(data, dict) else None) or "unknown"
                            failed_examples.append((str(car_ref), str(e)))
                        if isinstance(data, dict):
                            data["price_calc_failed"] = True
                        if car.get("data") is not data:
                            car["data"] = data
                print(
                    f"Price calc summary: ok={price_ok} failed={price_failed} total={len(cars)}",
                    file=sys.stderr,
                )
                for car_ref, err in failed_examples:
                    print(f"Price calc failed: car_id={car_ref} error={err}", file=sys.stderr)
            except ImportError as e:
                print(f"Warning: price module not found, export without prices: {e}", file=sys.stderr)

        if not args.no_sqlite_sync and cars:
            batch = []
            for car in cars:
                cid = car.get("id")
                if not cid:
                    continue
                batch.append((json.dumps(car, ensure_ascii=False), str(cid)))
            conn.executemany("UPDATE cars SET data_json = ? WHERE car_id = ?", batch)
            conn.commit()
            print(f"SQLite sync: updated data_json for {len(batch)} rows", file=sys.stderr)
    finally:
        conn.close()

    out = {
        "result": cars,
        "meta": {"page": 1, "next_page": 2, "limit": len(cars)},
    }
    out_path = Path(args.out).resolve()
    _write_json_atomic(out_path, out, gzip_enabled=args.gzip)

    if not args.no_facets_snapshot:
        repo_front = Path(__file__).resolve().parent.parent / "frontend"
        facets_path = repo_front / "data" / "catalog_facets.json"
        try:
            _write_catalog_facets_snapshot(db_path, facets_path)
            print(f"Facets snapshot: {facets_path}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: catalog facets snapshot failed: {e}", file=sys.stderr)

    if args.chunk_size and args.chunk_size > 0:
        chunk_dir = Path(args.chunk_dir).resolve()
        index_path = Path(args.chunk_index).resolve()
        files = []
        for page_num, chunk in _iter_chunks(cars, args.chunk_size):
            name = f"cars_{page_num:05d}.json"
            chunk_payload = {
                "result": chunk,
                "meta": {
                    "page": page_num,
                    "limit": len(chunk),
                    "total": len(cars),
                    "chunk_size": args.chunk_size,
                },
            }
            chunk_path = chunk_dir / name
            _write_json_atomic(chunk_path, chunk_payload, gzip_enabled=args.gzip)
            files.append({
                "page": page_num,
                "file": str(Path("data") / "chunks" / name).replace("\\", "/"),
                "count": len(chunk),
            })
        index_payload = {
            "total": len(cars),
            "chunk_size": args.chunk_size,
            "pages": len(files),
            "files": files,
        }
        _write_json_atomic(index_path, index_payload, gzip_enabled=args.gzip)
        print(f"Chunked export: {len(files)} files to {chunk_dir}")

    print(f"Exported {len(cars)} cars to {out_path}")

    repo_dir = Path(__file__).resolve().parent.parent
    run_learn = args.learn_engine_map or os.environ.get("AUTO_LEARN_ENGINE_MAP", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if run_learn:
        learn = Path(__file__).resolve().parent / "scripts" / "auto_learn_engine_map.py"
        if learn.is_file():
            lr = subprocess.run(
                [sys.executable, str(learn), "--repo", str(repo_dir)],
                cwd=str(repo_dir),
            )
            if lr.returncode != 0:
                print(f"Warning: auto_learn_engine_map.py exited {lr.returncode}", file=sys.stderr)
        else:
            print(f"Warning: script not found: {learn}", file=sys.stderr)


if __name__ == "__main__":
    main()
