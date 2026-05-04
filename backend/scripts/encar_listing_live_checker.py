#!/usr/bin/env python3
"""
Непрерывная проверка объявлений Encar в PostgreSQL: снято с продажи → encar_listing_sold=true.
Каталог и карточка читают флаг из API; ночной пайплайн по-прежнему может удалить строку.

Требуется миграция: infrastructure/postgresql/migrations/002_encar_listing_flags.sql

Примеры:
  # один проход (удобно для cron)
  python scripts/encar_listing_live_checker.py --config scraper_config.yaml --once

  # бесконечный цикл (systemd / screen)
  python scripts/encar_listing_live_checker.py --config scraper_config.yaml

Переменные окружения: DATABASE_URL или storage.postgres.dsn в YAML (как у encar_daily_update).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from pathlib import Path
from typing import Any, List, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from encar_listing_status import encar_listing_gone_from_api  # noqa: E402
from encar_scraper import AsyncEncarClient, load_config, setup_logging  # noqa: E402


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
    return config.get("listing_live_checker") or {}


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
                WHERE (source IS NULL OR source = 'encar')
                  AND (car_id IS NULL OR car_id NOT LIKE 'che168-%%')
                  AND encar_listing_sold = false
                  AND (
                    encar_listing_checked_at IS NULL
                    OR encar_listing_checked_at < (now() - (%s * interval '1 hour'))
                  )
                ORDER BY encar_listing_checked_at NULLS FIRST
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
                SET encar_listing_sold = %s,
                    encar_listing_checked_at = now(),
                    updated_at = now()
                WHERE car_id = %s
                """,
                (sold, car_id),
            )
        conn.commit()


async def _run_batch(
    *,
    client: AsyncEncarClient,
    log: Any,
    dsn: str,
    car_ids: Sequence[str],
    delay_min: float,
    delay_max: float,
) -> tuple[int, int, int]:
    """Returns (marked_sold, marked_active, skipped)."""
    sold_n = active_n = skip_n = 0
    for car_id in car_ids:
        data, status, err = await client.fetch_vehicle_detail(car_id)
        if status not in (200, 404, 410):
            log.warning("checker skip car_id=%s status=%s err=%s", car_id, status, err)
            skip_n += 1
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            continue
        gone = encar_listing_gone_from_api(int(status), data if isinstance(data, dict) else None)
        try:
            await asyncio.to_thread(_update_row_psycopg2, dsn, car_id, sold=gone)
        except Exception as e:
            log.exception("checker DB update failed car_id=%s: %s", car_id, e)
            skip_n += 1
        else:
            if gone:
                sold_n += 1
                log.info("checker sold car_id=%s http=%s", car_id, status)
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

    async with AsyncEncarClient(config, log) as client:
        while True:
            ids = await asyncio.to_thread(_fetch_batch_psycopg2, dsn, limit=batch, recheck_hours=recheck_h)
            if not ids:
                log.info("checker: нет машин к проверке, sleep %.0fs", idle)
                if args.once:
                    break
                await asyncio.sleep(idle)
                continue
            s, a, k = await _run_batch(
                client=client,
                log=log,
                dsn=dsn,
                car_ids=ids,
                delay_min=delay_min,
                delay_max=delay_max,
            )
            log.info("checker batch: sold=%s active=%s skip=%s", s, a, k)
            if args.once:
                break
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Encar listing live checker → encar_listing_sold in Postgres")
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
