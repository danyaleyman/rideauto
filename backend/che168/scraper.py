"""
Асинхронный скрейпер листинга Che168 → SQLite (таблица cars, source=che168).

Параметры в духе внешних API: brand, series, year, price_min/max, limit (потолок строк за прогон).
Пагинация: ?page=1,2,… на URL листинга PC.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
import yaml

from che168.client import DEFAULT_HEADERS, fetch_text
from che168.normalize import card_li_attrs_to_payload, row_matches_filters
from che168.parse import parse_cards_li_rows
from che168.urls import build_list_page_url

log = logging.getLogger("che168.scraper")


@dataclass
class ScrapeConfig:
    """Конфиг + CLI; значения как у «API» конкурентов."""

    db_path: str = "encar_cars.db"
    area: str = "china"
    brand: Optional[str] = None  # slug, напр. dazhong
    series: Optional[str] = None  # slug сегмента после марки
    list_path: Optional[str] = None  # полный path из адресной строки (перекрывает brand/series)
    year: Optional[int] = None  # если задан — и min и max = year
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_min: Optional[float] = None  # CNY
    price_max: Optional[float] = None  # CNY
    limit: int = 0  # 0 = без лимита; иначе макс. объявлений за прогон (кап 100)
    max_pages: int = 2000
    concurrency: int = 6
    cny_to_rub: float = 13.0
    mark_label: str = "中国二手车"
    request_timeout_s: float = 45.0
    delay_between_pages_s: float = 0.12
    parallel_pages: int = 3  # одновременно запрашиваемых страниц (чанк)
    cookie: Optional[str] = None  # сырой Cookie или env CHE168_COOKIE


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


def _apply_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_wra_cars_car_id_id ON cars(car_id, id DESC);
        CREATE INDEX IF NOT EXISTS idx_wra_data_mark ON cars(json_extract(data_json, '$.data.mark'));
        CREATE INDEX IF NOT EXISTS idx_wra_data_model ON cars(json_extract(data_json, '$.data.model'));
        """
    )
    conn.commit()


def _clamp_limit(v: int) -> int:
    if v <= 0:
        return 0
    return min(v, 100)


def _year_bounds(cfg: ScrapeConfig) -> Tuple[Optional[int], Optional[int]]:
    if cfg.year is not None:
        return cfg.year, cfg.year
    return cfg.year_min, cfg.year_max


def load_config_file(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def config_from_mapping(raw: Dict[str, Any], defaults: Optional[ScrapeConfig] = None) -> ScrapeConfig:
    base = defaults or ScrapeConfig()
    m = {k.replace("-", "_"): v for k, v in raw.items()}
    known = {f.name for f in ScrapeConfig.__dataclass_fields__.values()}
    for k, v in m.items():
        if k in known and v is not None:
            setattr(base, k, v)
    if base.cookie is None:
        env_c = (os.environ.get("CHE168_COOKIE") or "").strip()
        if env_c:
            base.cookie = env_c
    return base


async def _fetch_page(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout_s: float,
) -> Tuple[int, Optional[str]]:
    return await fetch_text(session, url, timeout_s=timeout_s)


def _headers_with_cookie(cookie: Optional[str]) -> Dict[str, str]:
    h = dict(DEFAULT_HEADERS)
    if cookie:
        h["Cookie"] = cookie
    return h


async def run_scrape(cfg: ScrapeConfig) -> int:
    """Возвращает число upsert в БД."""
    year_min, year_max = _year_bounds(cfg)
    lim = _clamp_limit(cfg.limit)

    db_path = str(Path(cfg.db_path).resolve())
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def sync_upsert_batch(batch: List[Tuple[str, str]]) -> int:
        if not batch:
            return 0
        conn = sqlite3.connect(db_path, timeout=120.0)
        try:
            _ensure_cars_schema(conn)
            conn.executemany(
                "INSERT OR REPLACE INTO cars (car_id, data_json, created_at) VALUES (?, ?, datetime('now'))",
                batch,
            )
            conn.commit()
        finally:
            conn.close()
        return len(batch)

    sem = asyncio.Semaphore(max(1, cfg.concurrency))
    headers = _headers_with_cookie(cfg.cookie)
    timeout = aiohttp.ClientTimeout(total=cfg.request_timeout_s + 30)
    connector = aiohttp.TCPConnector(limit=max(10, cfg.concurrency * 2))

    saved = 0
    seen_infoid: Set[str] = set()
    page = 1
    stop = False
    chunk = max(1, min(int(cfg.parallel_pages), 8))

    async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=connector) as session:
        while page <= cfg.max_pages and not stop:
            pages = list(range(page, min(page + chunk, cfg.max_pages + 1)))
            urls = [
                build_list_page_url(
                    area=cfg.area,
                    brand_slug=cfg.brand,
                    series_slug=cfg.series,
                    list_path=cfg.list_path,
                    page=p,
                )
                for p in pages
            ]

            async def _one(u: str) -> Tuple[int, Optional[str], str]:
                async with sem:
                    st, ht = await _fetch_page(session, u, timeout_s=cfg.request_timeout_s)
                return st, ht, u

            results = await asyncio.gather(*[_one(u) for u in urls])

            chunk_had_cards = False
            for pnum, (status, html, url) in zip(pages, results):
                if status != 200 or not html:
                    log.warning("page %s status=%s url=%s", pnum, status, url)
                    stop = True
                    break

                rows = parse_cards_li_rows(html)
                if rows:
                    chunk_had_cards = True

                batch: List[Tuple[str, str]] = []
                for attrs in rows:
                    if not row_matches_filters(
                        attrs,
                        year_min=year_min,
                        year_max=year_max,
                        price_min_cny=cfg.price_min,
                        price_max_cny=cfg.price_max,
                    ):
                        continue
                    offer_id = str(attrs.get("infoid") or "").strip()
                    if not offer_id or offer_id in seen_infoid:
                        continue
                    seen_infoid.add(offer_id)
                    payload = card_li_attrs_to_payload(
                        attrs,
                        cny_to_rub=cfg.cny_to_rub,
                        mark_fallback=cfg.mark_label,
                    )
                    car_id = f"che168-{offer_id}"
                    batch.append((car_id, json.dumps(payload, ensure_ascii=False)))
                    if lim and len(seen_infoid) >= lim:
                        stop = True
                        break

                if batch:
                    n = await asyncio.to_thread(sync_upsert_batch, batch)
                    saved += n
                    log.info("page %s: +%s rows (total saved %s)", pnum, n, saved)

                if stop:
                    break

            if stop:
                break
            if not chunk_had_cards:
                log.info("empty chunk starting page %s, stop", page)
                break

            page += len(pages)
            if cfg.delay_between_pages_s > 0:
                await asyncio.sleep(cfg.delay_between_pages_s)

    await asyncio.to_thread(_apply_indexes_after, db_path)
    return saved


def _apply_indexes_after(db_path: str) -> None:
    conn = sqlite3.connect(db_path, timeout=120.0)
    try:
        _ensure_cars_schema(conn)
        _apply_indexes(conn)
    finally:
        conn.close()


def setup_logging(level: str = "INFO") -> None:
    lv = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=lv, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def main(argv: Optional[List[str]] = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="Che168 async list scraper → SQLite")
    p.add_argument("--config", type=str, default=None, help="YAML (см. che168_scraper.yaml)")
    p.add_argument("--db", type=str, default=None)
    p.add_argument("--brand", type=str, default=None, help="Slug марки (dazhong, baoma, …)")
    p.add_argument("--series", type=str, default=None, help="Slug серии (второй сегмент path)")
    p.add_argument("--list-path", type=str, default=None, help="Полный path листинга из браузера")
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--year-min", type=int, default=None)
    p.add_argument("--year-max", type=int, default=None)
    p.add_argument("--price-min", type=float, default=None, help="Мин. цена, CNY")
    p.add_argument("--price-max", type=float, default=None, help="Макс. цена, CNY")
    p.add_argument("--limit", type=int, default=None, help="Макс. объявлений за прогон (1–100, 0=все)")
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--concurrency", type=int, default=None)
    p.add_argument("--parallel-pages", type=int, default=None, help="Страниц за раз (чанк), 1–8")
    p.add_argument("--cny-to-rub", type=float, default=None)
    p.add_argument("--log-level", type=str, default="INFO")
    args = p.parse_args(argv)

    cfg = ScrapeConfig()
    if args.config:
        cfg = config_from_mapping(load_config_file(args.config), cfg)
    if args.db is not None:
        cfg.db_path = args.db
    if args.brand is not None:
        cfg.brand = args.brand or None
    if args.series is not None:
        cfg.series = args.series or None
    if args.list_path is not None:
        cfg.list_path = args.list_path or None
    if args.year is not None:
        cfg.year = args.year
    if args.year_min is not None:
        cfg.year_min = args.year_min
    if args.year_max is not None:
        cfg.year_max = args.year_max
    if args.price_min is not None:
        cfg.price_min = args.price_min
    if args.price_max is not None:
        cfg.price_max = args.price_max
    if args.limit is not None:
        cfg.limit = args.limit
    if args.max_pages is not None:
        cfg.max_pages = args.max_pages
    if args.concurrency is not None:
        cfg.concurrency = args.concurrency
    if args.parallel_pages is not None:
        cfg.parallel_pages = max(1, min(8, args.parallel_pages))
    if args.cny_to_rub is not None:
        cfg.cny_to_rub = args.cny_to_rub

    setup_logging(args.log_level)
    t0 = time.perf_counter()
    n = asyncio.run(run_scrape(cfg))
    dt = time.perf_counter() - t0
    log.info("done: %s rows in %.1fs", n, dt)
    print(n, file=sys.stderr)


if __name__ == "__main__":
    main()
