"""CLI: fetch Che168 list pages and import JSON lines into SQLite (`cars` table)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, TextIO

import aiohttp

from che168.client import DEFAULT_HEADERS, fetch_text
from che168.normalize import listing_to_car_payload
from che168.parse import anchor_text_by_pairs, find_dealer_pairs


def _ensure_cars_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id TEXT UNIQUE NOT NULL,
            data_json TEXT NOT NULL,
            raw_json TEXT,
            created_at TEXT
        )
        """
    )


def import_payload_rows(conn: sqlite3.Connection, rows: Iterable[Dict[str, Any]]) -> int:
    """Upsert documents shaped like Encar: top-level `data` plus we pass car_id separately."""
    n = 0
    for row in rows:
        car_id = str(row.get("car_id") or "").strip()
        payload = row.get("payload")
        if not car_id or not isinstance(payload, dict):
            continue
        conn.execute(
            "INSERT OR REPLACE INTO cars (car_id, data_json, created_at) VALUES (?, ?, datetime('now'))",
            (car_id, json.dumps(payload, ensure_ascii=False)),
        )
        n += 1
    conn.commit()
    return n


async def _cmd_fetch_list(url: str, cny_to_rub: float, limit: int) -> None:
    timeout = aiohttp.ClientTimeout(total=60.0)
    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS, timeout=timeout) as session:
        status, html = await fetch_text(session, url)
        if status != 200 or not html:
            print(f"che168: fetch failed status={status}", file=sys.stderr)
            sys.exit(1)
    pairs = find_dealer_pairs(html)
    if limit > 0:
        pairs = pairs[:limit]
    texts = anchor_text_by_pairs(html)
    out_lines = []
    for dealer_id, offer_id in pairs:
        title = texts.get((dealer_id, offer_id), "")
        payload = listing_to_car_payload(dealer_id, offer_id, anchor_text=title, cny_to_rub=cny_to_rub)
        car_id = f"che168-{offer_id}"
        out_lines.append(json.dumps({"car_id": car_id, "payload": payload}, ensure_ascii=False))
    for line in out_lines:
        print(line)


def _read_jsonl(fp: TextIO) -> Iterable[Dict[str, Any]]:
    for line in fp:
        line = line.strip()
        if not line:
            continue
        yield json.loads(line)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Che168 list fetch + SQLite import")
    sub = p.add_subparsers(dest="cmd", required=True)

    fl = sub.add_parser("fetch-list", help="Download one list URL, print JSONL to stdout")
    fl.add_argument("--url", default="https://www.che168.com/china/list/", help="List page URL")
    fl.add_argument(
        "--cny-to-rub",
        type=float,
        default=13.0,
        help="Rough multiplier for my_price (CNY → RUB), default 13",
    )
    fl.add_argument("--limit", type=int, default=0, help="Max listings (0 = all found on page)")

    im = sub.add_parser("import-jsonl", help="Read JSONL from file or stdin into SQLite")
    im.add_argument("--db", type=Path, required=True, help="SQLite path (same as API --db)")
    im.add_argument(
        "--input",
        type=Path,
        default=None,
        help="JSONL file (default: stdin)",
    )

    args = p.parse_args(argv)

    if args.cmd == "fetch-list":
        asyncio.run(_cmd_fetch_list(args.url, args.cny_to_rub, args.limit))
        return

    if args.cmd == "import-jsonl":
        conn = sqlite3.connect(str(args.db.resolve()), timeout=120.0)
        try:
            _ensure_cars_schema(conn)
            if args.input:
                with open(args.input, encoding="utf-8") as fp:
                    n = import_payload_rows(conn, _read_jsonl(fp))
            else:
                n = import_payload_rows(conn, _read_jsonl(sys.stdin))
            print(f"imported {n} rows into {args.db}", file=sys.stderr)
        finally:
            conn.close()
        return


if __name__ == "__main__":
    main()
