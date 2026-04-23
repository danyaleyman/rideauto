#!/usr/bin/env python3
"""
Непрерывная проверка объявлений Dongchedi в PostgreSQL: снято с продажи → dongchedi_listing_sold=true.

Требуется миграция: infrastructure/postgresql/migrations/004_dongchedi_listing_flags.sql

Примеры:
  python scripts/dongchedi_listing_live_checker.py --config scraper_config.yaml --once
  python scripts/dongchedi_listing_live_checker.py --config scraper_config.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from pathlib import Path
from typing import Any, List, Sequence, Tuple

import aiohttp

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from encar_scraper import load_config, setup_logging  # noqa: E402


def _postgres_dsn(config: dict) -> str:
    storage_cfg = config.get("storage", {}) or {}
    dsn = (storage_cfg.get("postgres") or {}).get("dsn") or ""
    dsn = str(dsn).strip()
    if dsn:
        return dsn
    cp = config.get("checkpoint", {}) or {}
    pg_cp = cp.get("postgres")
    if isinstance(pg_cp, dict):
        d2 = str(pg_cp.get("dsn") or "").strip()
        if d2:
            return d2
    return (os.environ.get("DATABASE_URL") or "").strip()


def _checker_cfg(config: dict) -> dict:
    return config.get("dongchedi_listing_live_checker") or {}


def _fetch_batch_psycopg2(
    dsn: str,
    *,
    limit: int,
    recheck_hours: float,
) -> List[Tuple[str, str]]:
    import psycopg2

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT car_id, COALESCE(data->>'url', data->>'dongchedi_usedcar_url', '')
                FROM cars
                WHERE source = 'dongchedi'
                  AND dongchedi_listing_sold = false
                  AND (
                    dongchedi_listing_checked_at IS NULL
                    OR dongchedi_listing_checked_at < (now() - (%s * interval '1 hour'))
                  )
                ORDER BY dongchedi_listing_checked_at NULLS FIRST
                LIMIT %s
                """,
                (recheck_hours, limit),
            )
            out: List[Tuple[str, str]] = []
            for row in cur.fetchall():
                if not row:
                    continue
                cid = str(row[0] or "").strip()
                url = str(row[1] or "").strip()
                if cid and url:
                    out.append((cid, url))
            return out


def _update_row_psycopg2(dsn: str, car_id: str, *, sold: bool) -> None:
    import psycopg2

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cars
                SET dongchedi_listing_sold = %s,
                    dongchedi_listing_checked_at = now(),
                    updated_at = now()
                WHERE car_id = %s
                """,
                (sold, car_id),
            )
        conn.commit()


def _is_dongchedi_listing_gone(status: int, html: str) -> bool:
    if status in (404, 410):
        return True
    if status != 200:
        return False
    low = (html or "").lower()
    return any(
        marker in low
        for marker in (
            "该车源已下架",
            "已下架",
            "页面不存在",
            "car-source-offline",
            "source is offline",
        )
    )


async def _fetch_html(session: aiohttp.ClientSession, url: str) -> Tuple[int, str]:
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    }
    try:
        async with session.get(url, timeout=timeout, headers=headers, allow_redirects=True) as resp:
            text = await resp.text(encoding="utf-8", errors="replace")
            return int(resp.status), text
    except asyncio.TimeoutError:
        return 0, ""
    except aiohttp.ClientError:
        return 0, ""


async def _run_batch(
    *,
    session: aiohttp.ClientSession,
    log: Any,
    dsn: str,
    rows: Sequence[Tuple[str, str]],
    delay_min: float,
    delay_max: float,
) -> tuple[int, int, int]:
    sold_n = active_n = skip_n = 0
    for car_id, url in rows:
        status, html = await _fetch_html(session, url)
        if status == 0:
            log.warning("dongchedi checker skip car_id=%s status=%s", car_id, status)
            skip_n += 1
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            continue
        gone = _is_dongchedi_listing_gone(status, html)
        try:
            await asyncio.to_thread(_update_row_psycopg2, dsn, car_id, sold=gone)
        except Exception as e:
            log.exception("dongchedi checker DB update failed car_id=%s: %s", car_id, e)
            skip_n += 1
        else:
            if gone:
                sold_n += 1
                log.info("dongchedi checker sold car_id=%s http=%s", car_id, status)
            else:
                active_n += 1
        await asyncio.sleep(random.uniform(delay_min, delay_max))
    return sold_n, active_n, skip_n


async def amain(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser().resolve()
    config = load_config(str(cfg_path))
    log = setup_logging(config)
    dsn = _postgres_dsn(config)
    if not dsn:
        log.error("Нет DSN PostgreSQL (storage.postgres.dsn / DATABASE_URL)")
        return 2

    chk = _checker_cfg(config)
    batch = int(args.batch_size or chk.get("batch_size") or 35)
    batch = max(1, min(200, batch))
    recheck_h = float(args.recheck_hours if args.recheck_hours is not None else chk.get("recheck_hours") or 8.0)
    recheck_h = max(0.25, min(168.0, recheck_h))
    delay_min = float(args.delay_min or chk.get("delay_min", 0.35))
    delay_max = float(args.delay_max or chk.get("delay_max", 1.1))
    idle = float(args.idle_empty_sec or chk.get("idle_empty_sec") or 45.0)
    idle = max(5.0, min(600.0, idle))

    async with aiohttp.ClientSession() as session:
        while True:
            rows = await asyncio.to_thread(_fetch_batch_psycopg2, dsn, limit=batch, recheck_hours=recheck_h)
            if not rows:
                log.info("dongchedi checker: нет машин к проверке, sleep %.0fs", idle)
                if args.once:
                    break
                await asyncio.sleep(idle)
                continue
            s, a, k = await _run_batch(
                session=session,
                log=log,
                dsn=dsn,
                rows=rows,
                delay_min=delay_min,
                delay_max=delay_max,
            )
            log.info("dongchedi checker batch: sold=%s active=%s skip=%s", s, a, k)
            if args.once:
                break
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Dongchedi listing live checker → dongchedi_listing_sold in Postgres")
    p.add_argument("--config", default="scraper_config.yaml", help="Путь к scraper_config.yaml")
    p.add_argument("--once", action="store_true", help="Один проход и выход")
    p.add_argument("--batch-size", type=int, default=None, help="Размер пачки (override YAML)")
    p.add_argument("--recheck-hours", type=float, default=None, help="Не чаще раз в N часов для уже проверенных")
    p.add_argument("--delay-min", type=float, default=None)
    p.add_argument("--delay-max", type=float, default=None)
    p.add_argument("--idle-empty-sec", type=float, default=None, help="Пауза, если нечего проверять")
    args = p.parse_args()
    try:
        rc = asyncio.run(amain(args))
    except KeyboardInterrupt:
        rc = 130
    raise SystemExit(rc)


if __name__ == "__main__":
    main()

