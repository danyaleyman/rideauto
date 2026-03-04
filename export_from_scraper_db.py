"""
Export cars from scraper SQLite DB to cars.json (same format as parser_full save_to_file).
Usage: python export_from_scraper_db.py [--db encar_cars.db] [--out cars.json]
"""
import argparse
import json
import sqlite3


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="encar_cars.db", help="Scraper SQLite DB path")
    p.add_argument("--out", default="cars.json", help="Output JSON path")
    args = p.parse_args()
    conn = sqlite3.connect(args.db)
    rows = conn.execute("SELECT data_json FROM cars ORDER BY id").fetchall()
    cars = [json.loads(r[0]) for r in rows]
    conn.close()
    out = {
        "result": cars,
        "meta": {"page": 1, "next_page": 2, "limit": len(cars)},
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(cars)} cars to {args.out}")


if __name__ == "__main__":
    main()
