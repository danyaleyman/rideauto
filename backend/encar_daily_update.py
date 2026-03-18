"""
Daily update job for Encar DB: run at night (Asia/Yekaterinburg), discover new cars,
remove sold (404) from DB, then run scraper in --only-pending mode to fill details.
Uses same checkpoint and storage as encar_scraper.
"""
from __future__ import annotations

import asyncio
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Reuse scraper components
from encar_scraper import (
    AsyncEncarClient,
    Checkpoint,
    ChunkedJSONStorage,
    SQLiteStorage,
    _run_export_to_frontend,
    load_config,
    setup_logging,
)


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
    checkpoint: Checkpoint,
    config: dict,
    log,
) -> int:
    """Fetch first N list pages (by ModifiedDate), add new car IDs to pending. Returns count added."""
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
                if not car_id or checkpoint.is_collected(car_id):
                    continue
                to_add.append((car_id, car_type, item))
                if new_limit and (total_added + len(to_add)) >= new_limit:
                    break
            if to_add:
                added = checkpoint.add_pending_batch(to_add)
                total_added += added
                log.info("New cars car_type=%s offset=%s added=%s total_added=%s", car_type, offset, added, total_added)
            await asyncio.sleep(random.uniform(delay_min, delay_max))
        if new_limit and total_added >= new_limit:
            break
    return total_added


async def remove_sold(
    client: AsyncEncarClient,
    checkpoint: Checkpoint,
    storage,
    config: dict,
    log,
) -> int:
    """Sample cars from storage, re-fetch detail; if 404 remove from DB and collected. Returns count removed."""
    du = config.get("daily_update", {})
    sample = int(du.get("sold_check_sample", 500))
    d_min = float(du.get("sold_check_delay_min", 0.5))
    d_max = float(du.get("sold_check_delay_max", 1.2))

    ids = storage.get_car_ids_sample(sample)
    if not ids:
        log.info("No cars to check for sold (storage may be empty or not SQLite)")
        return 0
    removed = 0
    for car_id in ids:
        data, status, _ = await client.fetch_vehicle_detail(car_id)
        await asyncio.sleep(random.uniform(d_min, d_max))
        if status == 404 or (status == 200 and _is_sold(data)):
            try:
                storage.delete_car(car_id)
                checkpoint.remove_collected(car_id)
                removed += 1
                log.info("Removed sold car_id=%s status=%s", car_id, status)
            except Exception as e:
                log.warning("Failed to remove car_id=%s: %s", car_id, e)
    return removed


def _is_sold(data: dict | None) -> bool:
    if not data:
        return False
    # API may indicate sold via salesStatus or similar
    s = (data.get("salesStatus") or data.get("SalesStatus") or "").lower()
    if "sold" in s or "판매완료" in s:
        return True
    return False


def run_only_pending(config_path: str, log) -> bool:
    scraper_script = Path(__file__).resolve().parent / "encar_scraper.py"
    cmd = [sys.executable, str(scraper_script), "--config", config_path, "--only-pending"]
    log.info("Running: %s", " ".join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=False)
        return r.returncode == 0
    except Exception as e:
        log.exception("Subprocess failed: %s", e)
        return False


async def run_one_cycle(config_path: str, config: dict, log) -> None:
    checkpoint_cfg = config.get("checkpoint", {})
    cp_path = checkpoint_cfg.get("path", "scraper_checkpoint.db")
    max_pending = checkpoint_cfg.get("max_pending_ids", 500000)
    checkpoint = Checkpoint(path=cp_path, max_pending=max_pending)
    checkpoint.connect()

    storage_cfg = config.get("storage", {})
    backend = storage_cfg.get("backend", "sqlite")
    store_raw = storage_cfg.get("store_raw_responses", False)
    if backend == "sqlite":
        storage = SQLiteStorage(
            storage_cfg.get("sqlite", {}).get("path", "encar_cars.db"),
            store_raw=store_raw,
        )
        storage.connect()
    else:
        cj = storage_cfg.get("chunked_json", {})
        storage = ChunkedJSONStorage(
            cj.get("dir", "output_chunks"),
            cj.get("cars_per_file", 1000),
            store_raw=store_raw,
        )

    try:
        async with AsyncEncarClient(config, log) as client:
            added = await discover_new_cars(client, checkpoint, config, log)
            log.info("Discover new: added %s to pending", added)
            removed = await remove_sold(client, checkpoint, storage, config, log)
            log.info("Remove sold: removed %s cars", removed)
    finally:
        checkpoint.close()
        storage.close()

    run_only_pending(config_path, log)
    if backend == "sqlite":
        db_path = Path.cwd() / storage_cfg.get("sqlite", {}).get("path", "encar_cars.db")
        _run_export_to_frontend(str(db_path), log)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Encar daily update: discover new, remove sold, run --only-pending")
    p.add_argument("--config", default="scraper_config.yaml", help="Config YAML path")
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
