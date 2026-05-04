#!/usr/bin/env python3
"""
Проверка лотов Che168 Global в PostgreSQL: снят с публикации → che168_listing_sold=true.

Пример:
  python scripts/che168_listing_live_checker.py --config ../../che168_scraper.yaml --once
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, List, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from che168_scraper import setup_logging as che168_setup_logging  # noqa: E402
from encar_scraper import load_config  # noqa: E402
from scraper_pipeline.che168.api_outcome import (  # noqa: E402
    che168_carinfo_outcome,
    che168_response_suggests_session_refresh,
)
from scraper_pipeline.che168.client import AsyncChe168Client  # noqa: E402

_last_session_refresh_mono: float = 0.0


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
    return (config.get("listing_live_checker") or {}) or {}


def _to_infoid(car_id: str) -> str:
    s = str(car_id or "").strip()
    if s.lower().startswith("che168-"):
        return s.split("-", 1)[-1]
    return s


def _fetch_batch_psycopg2(
    dsn: str,
    *,
    limit: int,
    recheck_hours: float,
) -> List[str]:
    import psycopg2

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT car_id
                FROM cars
                WHERE lower(trim(source)) = 'che168'
                  AND che168_listing_sold = false
                  AND (
                    che168_listing_checked_at IS NULL
                    OR che168_listing_checked_at < (now() - (%s * interval '1 hour'))
                  )
                ORDER BY che168_listing_checked_at NULLS FIRST
                LIMIT %s
                """,
                (recheck_hours, limit),
            )
            return [str(r[0]) for r in cur.fetchall() if r and r[0]]


def _update_row_psycopg2(dsn: str, car_id: str, *, sold: bool) -> None:
    import psycopg2

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cars
                SET che168_listing_sold = %s,
                    che168_listing_checked_at = now(),
                    updated_at = now()
                WHERE car_id = %s
                """,
                (sold, car_id),
            )
        conn.commit()


async def _run_batch(
    *,
    client: AsyncChe168Client,
    log: Any,
    config: dict,
    dsn: str,
    car_ids: Sequence[str],
    delay_min: float,
    delay_max: float,
) -> tuple[int, int, int, int]:
    global _last_session_refresh_mono
    sold_n = active_n = skip_n = refresh_n = 0
    ch = config.get("che168") or {}
    for car_id in car_ids:
        infoid = _to_infoid(car_id)
        data, status, err = await client.fetch_carinfo(infoid)
        outcome = che168_carinfo_outcome(int(status), data if isinstance(data, dict) else None)
        if outcome == "retry" and che168_response_suggests_session_refresh(data):
            allow = ch.get("allow_runtime_session_refresh", True) is not False
            if allow:
                min_iv = float(ch.get("session_refresh_min_interval_sec", 90) or 90)
                now = time.monotonic()
                if now - _last_session_refresh_mono >= min_iv:
                    try:
                        from scraper_pipeline.che168.session_playwright import (
                            apply_playwright_bootstrap_to_config,
                        )

                        log.warning("che168 checker: session hint → Playwright bootstrap")
                        await asyncio.to_thread(apply_playwright_bootstrap_to_config, config, log)
                        client.reload_initial_cookies_from_config()
                        _last_session_refresh_mono = now
                        refresh_n += 1
                        data, status, err = await client.fetch_carinfo(infoid)
                    except ImportError as e:
                        log.error("che168 checker: Playwright недоступен — %s", e)
                    except Exception as e:
                        log.error("che168 checker: bootstrap failed — %s", e)
        if int(status) not in (200, 404, 410):
            log.warning("che168 checker skip car_id=%s status=%s err=%s", car_id, status, err)
            skip_n += 1
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            continue
        gone = che168_carinfo_outcome(int(status), data) == "gone"
        try:
            await asyncio.to_thread(_update_row_psycopg2, dsn, car_id, sold=gone)
        except Exception as e:
            log.exception("che168 checker DB failed car_id=%s: %s", car_id, e)
            skip_n += 1
        else:
            if gone:
                sold_n += 1
                log.info("che168 checker sold car_id=%s", car_id)
            else:
                active_n += 1
        await asyncio.sleep(random.uniform(delay_min, delay_max))
    return sold_n, active_n, skip_n, refresh_n


async def amain(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser().resolve()
    config = load_config(str(cfg_path))
    log = che168_setup_logging(config)
    _dev = (os.environ.get("CHE168_DEVICE_ID") or os.environ.get("CHE168_DEVICEID") or "").strip()
    if _dev:
        config.setdefault("che168", {})["deviceid"] = _dev

    dsn = _postgres_dsn(config)
    if not dsn:
        log.error("Нет DSN PostgreSQL")
        return 2

    chk = _checker_cfg(config)
    batch = int(args.batch_size or chk.get("batch_size") or 35)
    batch = max(1, min(200, batch))
    recheck_h = float(args.recheck_hours if args.recheck_hours is not None else chk.get("recheck_hours") or 8.0)
    recheck_h = max(0.25, min(168.0, recheck_h))
    delay_min = float(args.delay_min or chk.get("delay_min", 0.4))
    delay_max = float(args.delay_max or chk.get("delay_max", 1.2))
    idle = float(args.idle_empty_sec or chk.get("idle_empty_sec") or 45.0)
    idle = max(5.0, min(600.0, idle))

    prom_path = (os.environ.get("CHE168_LIVE_CHECKER_PROMETHEUS_TEXTFILE") or "").strip()
    if not prom_path:
        prom_path = str(chk.get("prometheus_textfile_path") or "").strip()

    run_totals = {"sold": 0, "active": 0, "skip": 0, "session_refreshes": 0}

    def _write_prom() -> None:
        if not prom_path:
            return
        try:
            from scraper_pipeline.che168.live_checker_prometheus import (
                write_che168_live_checker_prometheus_textfile,
            )

            write_che168_live_checker_prometheus_textfile(prom_path, run_totals)
        except Exception as e:
            log.warning("che168 checker prometheus textfile: %s", e)

    async with AsyncChe168Client(config, log) as client:
        while True:
            ids = await asyncio.to_thread(_fetch_batch_psycopg2, dsn, limit=batch, recheck_hours=recheck_h)
            if not ids:
                log.info("che168 checker: нечего проверять, sleep %.0fs", idle)
                _write_prom()
                if args.once:
                    break
                await asyncio.sleep(idle)
                continue
            s, a, k, r = await _run_batch(
                client=client,
                log=log,
                config=config,
                dsn=dsn,
                car_ids=ids,
                delay_min=delay_min,
                delay_max=delay_max,
            )
            run_totals["sold"] += s
            run_totals["active"] += a
            run_totals["skip"] += k
            run_totals["session_refreshes"] += r
            log.info(
                "che168 checker batch: sold=%s active=%s skip=%s session_refreshes=%s",
                s,
                a,
                k,
                r,
            )
            _write_prom()
            if args.once:
                break
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Che168 listing live checker → Postgres")
    p.add_argument("--config", default="che168_scraper.yaml", help="Путь к che168_scraper.yaml")
    p.add_argument("--once", action="store_true")
    p.add_argument("--batch-size", type=int, default=None)
    p.add_argument("--recheck-hours", type=float, default=None)
    p.add_argument("--delay-min", type=float, default=None)
    p.add_argument("--delay-max", type=float, default=None)
    p.add_argument("--idle-empty-sec", type=float, default=None)
    args = p.parse_args()
    try:
        rc = asyncio.run(amain(args))
    except KeyboardInterrupt:
        rc = 130
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
