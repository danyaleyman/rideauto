"""
Ежедневное обновление Encar: discover, remove sold (только Encar в PostgreSQL), затем scraper --only-pending.
Чекпоинт и каталог — PostgreSQL.
"""
from __future__ import annotations

import asyncio
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from encar_scraper import AsyncEncarClient, load_config, setup_logging
from scraper_pipeline.checkpoint_pg import CheckpointAsync


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


def _checkpoint_dsn(config: dict) -> str:
    return _postgres_dsn(config)


def next_run_at(tz_name: str, hour: int, minute: int) -> datetime:
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= today:
        today += timedelta(days=1)
    return today


def seconds_until(when: datetime) -> float:
    return (when - datetime.now(when.tzinfo)).total_seconds()


async def discover_new_cars(
    client: AsyncEncarClient,
    checkpoint: CheckpointAsync,
    config: dict,
    log,
) -> int:
    du = config.get("daily_update", {})
    pages = int(du.get("new_list_pages_per_run", 30))
    new_limit = int(du.get("new_cars_limit", 0) or 0)
    http_cfg = config.get("http", {})
    page_size = http_cfg.get("list_page_size", 100)
    delay_min = http_cfg.get("list_page_delay_min", 0.5)
    delay_max = http_cfg.get("list_page_delay_max", 1.5)
    car_types = config.get("car_types", ["for", "kor"])

    total_added = 0
    for car_type in car_types:
        for page in range(pages):
            if new_limit and total_added >= new_limit:
                break
            offset = page * page_size
            data, status, err = await client.fetch_list_page(offset, page_size, car_type)
            if status != 200 or not data:
                log.warning("List page car_type=%s offset=%s status=%s err=%s", car_type, offset, status, err)
                continue
            items = data.get("SearchResults") or []
            if not items:
                break
            to_add = []
            for item in items:
                car_id = str(item.get("Id", ""))
                if not car_id or await checkpoint.is_collected(car_id):
                    continue
                to_add.append((car_id, car_type, item))
                if new_limit and (total_added + len(to_add)) >= new_limit:
                    break
            if to_add:
                added = await checkpoint.add_pending_batch(to_add)
                total_added += added
                log.info("New cars car_type=%s offset=%s added=%s total_added=%s", car_type, offset, added, total_added)
            await asyncio.sleep(random.uniform(delay_min, delay_max))
        if new_limit and total_added >= new_limit:
            break
    return total_added


async def remove_sold_postgres(
    client: AsyncEncarClient,
    checkpoint: CheckpointAsync,
    dsn: str,
    config: dict,
    log,
) -> int:
    try:
        import psycopg2  # type: ignore[import-untyped]
    except ImportError:
        log.warning("Remove sold: psycopg2 не установлен — пропуск")
        return 0

    du = config.get("daily_update", {})
    sample = int(du.get("sold_check_sample", 500))
    if sample <= 0:
        log.info("Remove sold: sold_check_sample=%s — пропуск за этот цикл", sample)
        return 0
    d_min = float(du.get("sold_check_delay_min", 0.5))
    d_max = float(du.get("sold_check_delay_max", 1.2))

    def _fetch_ids() -> list[str]:
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT car_id FROM cars
                    WHERE (source IS NULL OR source = 'encar')
                      AND car_id NOT LIKE 'dongchedi-%%'
                    ORDER BY RANDOM()
                    LIMIT %s
                    """,
                    (sample,),
                )
                return [str(r[0]) for r in cur.fetchall() if r and r[0]]

    ids = await asyncio.to_thread(_fetch_ids)
    if not ids:
        log.info("Remove sold: нет строк Encar для выборки")
        return 0

    def _delete(cid: str) -> None:
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cars WHERE car_id = %s", (cid,))
            conn.commit()

    removed = 0
    for car_id in ids:
        data, status, _ = await client.fetch_vehicle_detail(car_id)
        await asyncio.sleep(random.uniform(d_min, d_max))
        if status == 404 or (status == 200 and _is_sold(data)):
            try:
                await asyncio.to_thread(_delete, car_id)
                await checkpoint.remove_collected(car_id)
                removed += 1
                log.info("Removed sold car_id=%s status=%s (postgres)", car_id, status)
            except Exception as e:
                log.warning("Failed to remove car_id=%s from postgres: %s", car_id, e)
    return removed


def _is_sold(data: dict | None) -> bool:
    if not data:
        return False
    s = (data.get("salesStatus") or data.get("SalesStatus") or "").lower()
    if "sold" in s or "판매완료" in s:
        return True
    return False


def run_only_pending(config_path: str, log) -> bool:
    scraper_script = Path(__file__).resolve().parent / "encar_scraper.py"
    cfg_abs = str(Path(config_path).expanduser().resolve())
    cmd = [sys.executable, str(scraper_script), "--config", cfg_abs, "--only-pending"]
    log.info("Running: %s", " ".join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=False)
        return r.returncode == 0
    except Exception as e:
        log.exception("Subprocess failed: %s", e)
        return False


async def run_one_cycle(config_path: str, config: dict, log) -> None:
    checkpoint_cfg = config.get("checkpoint", {})
    max_pending = int(checkpoint_cfg.get("max_pending_ids", 500000))
    scope = str(checkpoint_cfg.get("scope", "encar")).strip() or "encar"
    dsn = _checkpoint_dsn(config)
    if not dsn:
        raise ValueError("encar_daily_update: нужен DATABASE_URL или storage.postgres.dsn")
    checkpoint = CheckpointAsync(dsn=dsn, scope=scope, max_pending=max_pending)
    await checkpoint.connect()

    try:
        async with AsyncEncarClient(config, log) as client:
            added = await discover_new_cars(client, checkpoint, config, log)
            log.info("Discover new: added %s to pending", added)
            removed = await remove_sold_postgres(client, checkpoint, dsn, config, log)
            log.info("Remove sold: removed %s cars", removed)
    finally:
        await checkpoint.close()

    run_only_pending(config_path, log)


def main() -> None:
    import argparse

    _repo_root = Path(__file__).resolve().parent.parent
    _default_cfg = _repo_root / "scraper_config.yaml"
    p = argparse.ArgumentParser(description="Encar daily update: discover new, remove sold, run --only-pending")
    p.add_argument("--config", default=str(_default_cfg), help="Config YAML path (default: repo root scraper_config.yaml)")
    p.add_argument("--once", action="store_true", help="Run one cycle and exit (no scheduler)")
    args = p.parse_args()

    config = load_config(args.config)
    log = setup_logging(config)
    du = config.get("daily_update", {})
    tz_name = du.get("timezone", "Asia/Yekaterinburg")
    run_at_hour = int(du.get("run_at_hour", 3))
    run_at_minute = int(du.get("run_at_minute", 0))

    if args.once:
        asyncio.run(run_one_cycle(args.config, config, log))
        return

    log.info("Daily update scheduler: run at %02d:%02d %s", run_at_hour, run_at_minute, tz_name)
    while True:
        next_run = next_run_at(tz_name, run_at_hour, run_at_minute)
        wait = max(0, seconds_until(next_run))
        if wait > 0:
            log.info("Next run at %s (in %.0f s)", next_run.isoformat(), wait)
            time.sleep(wait)
        log.info("Starting daily update cycle")
        asyncio.run(run_one_cycle(args.config, config, log))
        log.info("Daily update cycle finished")


if __name__ == "__main__":
    main()
