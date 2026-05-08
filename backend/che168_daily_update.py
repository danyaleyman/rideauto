"""
Ежедневное обновление Che168: discover, remove sold (только China в PostgreSQL), затем scraper --only-pending.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from zoneinfo import ZoneInfo

from che168_scraper import load_config, setup_logging
from scraper_pipeline.checkpoint_pg import CheckpointAsync
from scraper_pipeline.che168.api_outcome import che168_carinfo_outcome
from scraper_pipeline.che168.client import AsyncChe168Client, ensure_che168_deviceid
from scraper_pipeline.che168.workers import (
    _returncode_ok,
    build_segments,
    che168_brand_id,
    che168_brand_rows,
    che168_listing_numeric_id,
    che168_search_items,
)


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


def _daily_cfg(config: dict) -> dict:
    du = config.get("daily_update")
    if isinstance(du, dict):
        return du
    return {}


def _chunked(items: Sequence[str], size: int) -> Iterable[list[str]]:
    step = max(1, int(size or 1))
    for i in range(0, len(items), step):
        yield list(items[i : i + step])


def _external_infoid_from_car_id(car_id: str) -> str:
    s = str(car_id or "").strip()
    if s.lower().startswith("che168-"):
        return s.split("-", 1)[1].strip()
    return s


def _slack_credentials_from_env() -> tuple[str, str, str]:
    webhook = (os.environ.get("OPS_SLACK_WEBHOOK") or "").strip()
    bot_token = (os.environ.get("OPS_SLACK_BOT_TOKEN") or "").strip()
    channel_id = (os.environ.get("OPS_SLACK_CHANNEL_ID") or "").strip()
    return webhook, bot_token, channel_id


def _notify_slack(text: str, config: dict, log) -> None:
    try:
        from scripts.slack_ops import notify_slack_alert
    except Exception as e:
        log.debug("Slack notify unavailable: %s", e)
        return
    du = _daily_cfg(config)
    webhook = str(du.get("slack_webhook") or "").strip()
    bot_token = str(du.get("slack_bot_token") or "").strip()
    channel_id = str(du.get("slack_channel_id") or "").strip()
    if not (webhook or (bot_token and channel_id)):
        ew, eb, ec = _slack_credentials_from_env()
        webhook = webhook or ew
        bot_token = bot_token or eb
        channel_id = channel_id or ec
    if not (webhook or (bot_token and channel_id)):
        return
    try:
        notify_slack_alert(text[:39000], webhook_url=webhook, bot_token=bot_token, channel_id=channel_id)
    except Exception as e:
        log.warning("Slack notify failed: %s", e)


def _write_daily_prometheus_textfile(path: str, stats: dict[str, Any], log) -> None:
    p = str(path or "").strip()
    if not p:
        return
    fp = Path(p)
    fp.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HELP che168_daily_new_cars New listings discovered in last run.",
        "# TYPE che168_daily_new_cars gauge",
        f"che168_daily_new_cars {int(stats.get('new_cars_added', 0) or 0)}",
        "# HELP che168_daily_sold_cars Sold listings removed in last run.",
        "# TYPE che168_daily_sold_cars gauge",
        f"che168_daily_sold_cars {int(stats.get('sold_cars_removed', 0) or 0)}",
        "# HELP che168_daily_pending Pending queue size after cycle.",
        "# TYPE che168_daily_pending gauge",
        f"che168_daily_pending {int(stats.get('pending_queue_size', 0) or 0)}",
        "# HELP che168_daily_last_run_unixtime Daily update finish time.",
        "# TYPE che168_daily_last_run_unixtime gauge",
        f"che168_daily_last_run_unixtime {int(time.time())}",
        "",
    ]
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(fp)
    log.debug("Che168 daily prometheus textfile written: %s", fp)


def next_run_at(tz_name: str, hour: int, minute: int) -> datetime:
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


def seconds_until(when: datetime) -> float:
    return (when - datetime.now(when.tzinfo)).total_seconds()


async def discover_new_cars(
    client: AsyncChe168Client,
    checkpoint: CheckpointAsync,
    config: dict,
    log,
) -> int:
    du = _daily_cfg(config)
    ch = config.get("che168", {}) if isinstance(config.get("che168"), dict) else {}
    pages = int(du.get("new_list_pages_per_run", 10) or 10)
    new_limit = int(du.get("new_cars_limit", 0) or 0)
    pagesize = int(ch.get("search_pagesize", 20) or 20)
    sort = int(ch.get("search_sort", 0) or 0)
    vehicle_list = int(ch.get("vehicle_list", 0) or 0)
    delay_min = float(du.get("new_check_delay_min", 0.4) or 0.4)
    delay_max = float(du.get("new_check_delay_max", 1.2) or 1.2)
    max_brands = max(1, int(du.get("new_brand_sample", 25) or 25))

    ch = config.get("che168", {}) if isinstance(config.get("che168"), dict) else {}
    seg_cfg = ch.get("segmentation") if isinstance(ch.get("segmentation"), dict) else {}
    seg_enabled = bool(seg_cfg.get("enabled"))
    segments = build_segments(seg_cfg) if seg_enabled else [{}]
    # Чтобы daily-update не стал "mini-full-scan": ограничим число сегментов на бренд.
    max_segments_per_brand_daily = int(du.get("new_discovery_segments_per_brand", 10) or 10)
    if max_segments_per_brand_daily > 0:
        segments = segments[:max_segments_per_brand_daily]

    total_added = 0
    brands_raw, st, err = await client.fetch_brands()
    if st != 200 or not brands_raw or not _returncode_ok(brands_raw):
        log.warning("Che168 daily discover: /brand failed status=%s err=%s", st, err)
        return 0
    rows = che168_brand_rows(brands_raw)
    if not rows:
        return 0
    configured = ch.get("brand_ids") if isinstance(ch.get("brand_ids"), list) else []
    configured_ids = [int(x) for x in configured if str(x).strip().isdigit()]
    candidate_ids: list[int] = configured_ids or [bid for r in rows if (bid := che168_brand_id(r)) is not None]
    candidate_ids = candidate_ids[:max_brands]

    for brand_id in candidate_ids:
        if new_limit and total_added >= new_limit:
            break
        for segment in segments:
            if new_limit and total_added >= new_limit:
                break
            segment_key = str(segment.get("key") or "default").strip()
            ck_key = f"daily_brand_{brand_id}_segment_{segment_key}_page"
            start_page = int(await checkpoint.get_last_offset(ck_key) or 1)
            if start_page < 1:
                start_page = 1

            for page in range(start_page, start_page + pages):
                if new_limit and total_added >= new_limit:
                    break

                data, status, err = await client.fetch_search(
                    brandid=int(brand_id),
                    pageindex=page,
                    pagesize=pagesize,
                    sort=sort,
                    vehicle_list=vehicle_list,
                    price_min=segment.get("price_min"),
                    price_max=segment.get("price_max"),
                    year_min=segment.get("year_min"),
                    year_max=segment.get("year_max"),
                )
                if status != 200 or not data or not _returncode_ok(data):
                    log.warning(
                        "Che168 daily discover: brand=%s seg=%s page=%s status=%s err=%s",
                        brand_id,
                        segment_key,
                        page,
                        status,
                        err,
                    )
                    break
                items = che168_search_items(data)
                if not items:
                    break
                to_add: list[tuple[str, str, Any]] = []
                for item in items:
                    ext = che168_listing_numeric_id(item)
                    if not ext:
                        continue
                    if await checkpoint.is_collected(ext):
                        continue
                    to_add.append((ext, "che168", item))
                    if new_limit and (total_added + len(to_add)) >= new_limit:
                        break
                if to_add:
                    added = await checkpoint.add_pending_batch(to_add)
                    total_added += int(added)
                    log.info(
                        "Che168 daily discover brand=%s seg=%s page=%s added=%s total=%s",
                        brand_id,
                        segment_key,
                        page,
                        added,
                        total_added,
                    )
                await checkpoint.set_last_offset(ck_key, page + 1)
                await asyncio.sleep(random.uniform(delay_min, delay_max))

    log.info(
        "Che168 daily discover: seg_enabled=%s segments=%s max_segments_per_brand_daily=%s new_limit=%s total_added=%s",
        seg_enabled,
        len(segments),
        max_segments_per_brand_daily,
        new_limit,
        total_added,
    )
    return total_added


async def remove_sold_postgres(
    client: AsyncChe168Client,
    checkpoint: CheckpointAsync,
    dsn: str,
    config: dict,
    log,
) -> int:
    try:
        import psycopg2  # type: ignore[import-untyped]
    except ImportError:
        log.warning("Che168 remove sold: psycopg2 not installed")
        return 0
    du = _daily_cfg(config)
    sample = int(du.get("sold_check_sample", 500) or 500)
    if sample <= 0:
        return 0
    d_min = float(du.get("sold_check_delay_min", 0.4) or 0.4)
    d_max = float(du.get("sold_check_delay_max", 1.2) or 1.2)
    retry_attempts = max(1, int(du.get("sold_check_retry_attempts", 3) or 3))
    delete_batch_size = max(1, int(du.get("sold_delete_batch_size", 50) or 50))

    def _fetch_ids() -> list[str]:
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT car_id FROM cars
                    WHERE lower(trim(source)) = 'che168'
                      AND car_id LIKE 'che168-%%'
                    ORDER BY COALESCE(updated_at, created_at) ASC, car_id ASC
                    LIMIT %s
                    """,
                    (sample,),
                )
                return [str(r[0]) for r in cur.fetchall() if r and r[0]]

    def _batch_delete(car_ids: list[str]) -> list[str]:
        if not car_ids:
            return []
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cars WHERE car_id = ANY(%s) RETURNING car_id", (car_ids,))
                rows = cur.fetchall() or []
            conn.commit()
        return [str(r[0]) for r in rows if r and r[0]]

    async def _fetch_with_retry(infoid: str, max_attempts: int) -> tuple[Optional[Any], int, Optional[str]]:
        status = 0
        err: Optional[str] = None
        for attempt in range(max_attempts):
            data, status, err = await client.fetch_carinfo(infoid)
            if status in (200, 404, 410):
                return data, status, err
            await asyncio.sleep(1.5**attempt)
        return None, status, err

    ids = await asyncio.to_thread(_fetch_ids)
    if not ids:
        return 0
    to_delete: list[str] = []
    for car_id in ids:
        infoid = _external_infoid_from_car_id(car_id)
        if not infoid:
            continue
        data, status, err = await _fetch_with_retry(infoid, max_attempts=retry_attempts)
        outcome = che168_carinfo_outcome(int(status or 0), data)
        if outcome == "gone":
            to_delete.append(car_id)
        elif int(status or 0) not in (200,):
            log.debug("Che168 remove sold skip car_id=%s infoid=%s status=%s err=%s", car_id, infoid, status, err)
        await asyncio.sleep(random.uniform(d_min, d_max))

    removed = 0
    for batch in _chunked(to_delete, delete_batch_size):
        try:
            deleted = await asyncio.to_thread(_batch_delete, batch)
            for car_id in deleted:
                await checkpoint.remove_collected(_external_infoid_from_car_id(car_id))
            removed += len(deleted)
        except Exception as e:
            log.warning("Che168 remove sold batch failed size=%s: %s", len(batch), e)
    return int(removed)


def run_only_pending(config_path: str, log) -> bool:
    scraper_script = Path(__file__).resolve().parent / "che168_scraper.py"
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
    scope = str(checkpoint_cfg.get("scope", "che168")).strip() or "che168"
    dsn = _postgres_dsn(config)
    if not dsn:
        raise ValueError("che168_daily_update: нужен DATABASE_URL или storage.postgres.dsn")
    try:
        import psycopg2  # type: ignore[import-untyped]
    except ImportError as e:
        raise ValueError("che168_daily_update: psycopg2 required for advisory lock") from e

    du = _daily_cfg(config)
    lock_id = int(du.get("advisory_lock_id", 4242) or 4242)
    lock_conn = psycopg2.connect(dsn)
    lock_conn.autocommit = True
    with lock_conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,))
        row = cur.fetchone()
        got_lock = bool(row and row[0])
    if not got_lock:
        log.warning("Another che168 daily_update is running (lock_id=%s), skipping", lock_id)
        lock_conn.close()
        return

    checkpoint = CheckpointAsync(dsn=dsn, scope=scope, max_pending=max_pending)
    await checkpoint.connect()
    cycle_stats: dict[str, Any] = {"new_cars_added": 0, "sold_cars_removed": 0, "pending_queue_size": 0}
    try:
        ensure_che168_deviceid(config, log)
        async with AsyncChe168Client(config, log) as client:
            added = await discover_new_cars(client, checkpoint, config, log)
            removed = await remove_sold_postgres(client, checkpoint, dsn, config, log)
            pending = await checkpoint.pending_count()
            cycle_stats["new_cars_added"] = int(added)
            cycle_stats["sold_cars_removed"] = int(removed)
            cycle_stats["pending_queue_size"] = int(pending)
            log.info("Che168 daily cycle: new=%s sold_removed=%s pending=%s", added, removed, pending)
    finally:
        await checkpoint.close()
        try:
            with lock_conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
        finally:
            lock_conn.close()

    prom = str(du.get("prometheus_textfile_path") or "").strip()
    if prom:
        _write_daily_prometheus_textfile(prom, cycle_stats, log)

    ok = run_only_pending(config_path, log)
    if ok:
        _notify_slack(
            f"*Che168 daily update*: OK\nnew={cycle_stats['new_cars_added']} sold_removed={cycle_stats['sold_cars_removed']} pending={cycle_stats['pending_queue_size']}",
            config,
            log,
        )
    else:
        _notify_slack(
            f"*Che168 daily update*: FAILED\nnew={cycle_stats['new_cars_added']} sold_removed={cycle_stats['sold_cars_removed']} pending={cycle_stats['pending_queue_size']}\nStep `che168_scraper --only-pending` returned non-zero.",
            config,
            log,
        )


def main() -> None:
    _repo_root = Path(__file__).resolve().parent.parent
    default_cfg = _repo_root / "che168_scraper.yaml"
    p = argparse.ArgumentParser(description="Che168 daily update: discover new, remove sold, run --only-pending")
    p.add_argument("--config", default=str(default_cfg), help="Config YAML path (default: repo root che168_scraper.yaml)")
    p.add_argument("--once", action="store_true", help="Run one cycle and exit (no scheduler)")
    args = p.parse_args()

    config = load_config(args.config)
    log = setup_logging(config)
    du = _daily_cfg(config)
    tz_name = str(du.get("timezone", "Asia/Yekaterinburg"))
    run_at_hour = int(du.get("run_at_hour", 1))
    run_at_minute = int(du.get("run_at_minute", 30))

    if args.once:
        asyncio.run(run_one_cycle(args.config, config, log))
        return

    log.info("Che168 daily scheduler: run at %02d:%02d %s", run_at_hour, run_at_minute, tz_name)
    while True:
        next_run = next_run_at(tz_name, run_at_hour, run_at_minute)
        wait = max(0, seconds_until(next_run))
        if wait > 0:
            log.info("Next run at %s (in %.0f s)", next_run.isoformat(), wait)
            time.sleep(wait)
        log.info("Starting Che168 daily cycle")
        asyncio.run(run_one_cycle(args.config, config, log))
        log.info("Che168 daily cycle finished")


if __name__ == "__main__":
    main()
