"""
Export cars from scraper SQLite DB to frontend JSON.

- Full file: cars.json (legacy frontend format).
- Optional chunked export: chunks + index file.
- Optional gzip for better CDN/static delivery.
"""
import argparse
import gzip
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


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


def _write_json(path: Path, payload: dict, gzip_enabled: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if gzip_enabled:
        with gzip.open(str(path) + ".gz", "wt", encoding="utf-8") as gz:
            json.dump(payload, gz, ensure_ascii=False)


def _iter_chunks(items, chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield i // chunk_size + 1, items[i:i + chunk_size]


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
        "--learn-engine-map",
        action="store_true",
        help="После экспорта запустить auto_learn_engine_map.py (обновить engine_map.json по motorType)",
    )
    args = p.parse_args()
    conn = sqlite3.connect(args.db)
    rows = conn.execute("SELECT car_id, data_json FROM cars ORDER BY id").fetchall()
    cars = []
    for car_id, data_json in rows:
        car = json.loads(data_json)
        # Единый стабильный id для ссылок каталог → карточка (Encar car_id)
        car["id"] = car_id
        if isinstance(car.get("data"), dict):
            car["data"]["id"] = str(car_id)
            if not args.no_power_lookup:
                _fill_power_from_external(car["data"])
        cars.append(car)
    conn.close()

    if not args.no_prices and cars:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from price import PriceCalculator
            calc = PriceCalculator()
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

    out = {
        "result": cars,
        "meta": {"page": 1, "next_page": 2, "limit": len(cars)},
    }
    out_path = Path(args.out).resolve()
    _write_json(out_path, out, gzip_enabled=args.gzip)

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
            _write_json(chunk_path, chunk_payload, gzip_enabled=args.gzip)
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
        _write_json(index_path, index_payload, gzip_enabled=args.gzip)
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
