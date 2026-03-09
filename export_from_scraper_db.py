"""
Export cars from scraper SQLite DB to cars.json (same format as parser_full save_to_file).
Рассчитанные цены (растаможка 2026, KRW→USDT→RUB, брокер, 10%) добавляются в каждую карточку.
Usage: python export_from_scraper_db.py [--db encar_cars.db] [--out cars.json] [--no-prices]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="encar_cars.db", help="Scraper SQLite DB path")
    p.add_argument("--out", default="cars.json", help="Output JSON path")
    p.add_argument("--no-prices", action="store_true", help="Do not calculate prices (no API calls)")
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
        cars.append(car)
    conn.close()

    if not args.no_prices and cars:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from price import PriceCalculator
            calc = PriceCalculator()
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
                except Exception as e:
                    if i == 0:
                        print(f"Warning: price calc failed for first car: {e}", file=sys.stderr)
                    if isinstance(data, dict):
                        data["price_calc_failed"] = True
                    if car.get("data") is not data:
                        car["data"] = data
        except ImportError as e:
            print(f"Warning: price module not found, export without prices: {e}", file=sys.stderr)

    out = {
        "result": cars,
        "meta": {"page": 1, "next_page": 2, "limit": len(cars)},
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(cars)} cars to {args.out}")


if __name__ == "__main__":
    main()
