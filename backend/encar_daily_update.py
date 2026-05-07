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
from typing import Any, Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

from encar_listing_status import encar_detail_indicates_sold
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


def _daily_cfg(config: dict) -> dict:
    return config.get("daily_update", {}) if isinstance(config.get("daily_update"), dict) else {}


def _chunked(items: Sequence[str], size: int) -> Iterable[list[str]]:
    step = max(1, int(size or 1))
    for i in range(0, len(items), step):
        yield list(items[i : i + step])


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
        "# HELP encar_daily_new_cars New cars discovered in last run.",
        "# TYPE encar_daily_new_cars gauge",
        f"encar_daily_new_cars {int(stats.get('new_cars_added', 0) or 0)}",
        "# HELP encar_daily_sold_cars Sold cars removed in last run.",
        "# TYPE encar_daily_sold_cars gauge",
        f"encar_daily_sold_cars {int(stats.get('sold_cars_removed', 0) or 0)}",
        "# HELP encar_daily_pending Pending queue size after cycle.",
        "# TYPE encar_daily_pending gauge",
        f"encar_daily_pending {int(stats.get('pending_queue_size', 0) or 0)}",
        "# HELP encar_daily_last_run_unixtime Daily update finish time.",
        "# TYPE encar_daily_last_run_unixtime gauge",
        f"encar_daily_last_run_unixtime {int(time.time())}",
        "",
    ]
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(fp)
    log.debug("Daily update prometheus textfile written: %s", fp)


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
                hint = ""
                if status == 407:
                    hint = " — 407 Proxy-Authenticate: проверьте ENCAR_PROXY_URLS (логин/пароль в кабинете FloppyData, спецсимволы в URL как %40 для @)"
                log.warning("List page car_type=%s offset=%s status=%s err=%s%s", car_type, offset, status, err, hint)
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
    retry_attempts = max(1, int(du.get("sold_check_retry_attempts", 3) or 3))
    delete_batch_size = max(1, int(du.get("sold_delete_batch_size", 50) or 50))

    def _fetch_ids() -> list[str]:
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT car_id FROM cars
                    WHERE (source IS NULL OR source = 'encar')
                      AND (car_id IS NULL OR car_id NOT LIKE 'che168-%%')
                    ORDER BY COALESCE(updated_at, created_at) ASC, car_id ASC
                    LIMIT %s
                    """,
                    (sample,),
                )
                return [str(r[0]) for r in cur.fetchall() if r and r[0]]

    ids = await asyncio.to_thread(_fetch_ids)
    if not ids:
        log.info("Remove sold: нет строк Encar для выборки")
        return 0

    async def _fetch_with_retry(car_id: str, max_attempts: int) -> tuple[Optional[dict], int, Optional[str]]:
        status = 0
        err: Optional[str] = None
        for attempt in range(max_attempts):
            data, status, err = await client.fetch_vehicle_detail(car_id)
            if status in (200, 404):
                return data, status, err
            await asyncio.sleep(1.5**attempt)
        return None, status, err

    def _batch_delete(car_ids: List[str]) -> list[str]:
        if not car_ids:
            return []
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cars WHERE car_id = ANY(%s) RETURNING car_id",
                    (car_ids,),
                )
                rows = cur.fetchall() or []
            conn.commit()
        return [str(r[0]) for r in rows if r and r[0]]

    removed_ids: list[str] = []
    for car_id in ids:
        data, status, err = await _fetch_with_retry(car_id, max_attempts=retry_attempts)
        await asyncio.sleep(random.uniform(d_min, d_max))
        if status == 404 or (status == 200 and encar_detail_indicates_sold(data)):
            removed_ids.append(car_id)
        elif status not in (200,):
            log.debug("Remove sold: skip car_id=%s status=%s err=%s", car_id, status, err)

    removed = 0
    for batch in _chunked(removed_ids, delete_batch_size):
        try:
            deleted = await asyncio.to_thread(_batch_delete, batch)
            for car_id in deleted:
                await checkpoint.remove_collected(car_id)
            removed += len(deleted)
            log.info("Remove sold batch: requested=%s deleted=%s", len(batch), len(deleted))
        except Exception as e:
            log.warning("Failed sold batch delete size=%s: %s", len(batch), e)
    return int(removed)


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
    try:
        import psycopg2  # type: ignore[import-untyped]
    except ImportError as e:
        raise ValueError("encar_daily_update: psycopg2 required for advisory lock") from e

    du = _daily_cfg(config)
    lock_id = int(du.get("advisory_lock_id", 42) or 42)
    lock_conn = psycopg2.connect(dsn)
    lock_conn.autocommit = True
    got_lock = False
    with lock_conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,))
        row = cur.fetchone()
        got_lock = bool(row and row[0])
    if not got_lock:
        log.warning("Another daily_update is already running (lock_id=%s), skipping", lock_id)
        lock_conn.close()
        return

    checkpoint = CheckpointAsync(dsn=dsn, scope=scope, max_pending=max_pending)
    await checkpoint.connect()
    cycle_stats: dict[str, Any] = {"new_cars_added": 0, "sold_cars_removed": 0, "pending_queue_size": 0}

    try:
        async with AsyncEncarClient(config, log) as client:
            added = await discover_new_cars(client, checkpoint, config, log)
            log.info("Discover new: added %s to pending", added)
            removed = await remove_sold_postgres(client, checkpoint, dsn, config, log)
            log.info("Remove sold: removed %s cars", removed)
            pending = await checkpoint.pending_count()
            cycle_stats["new_cars_added"] = int(added)
            cycle_stats["sold_cars_removed"] = int(removed)
            cycle_stats["pending_queue_size"] = int(pending)
    finally:
        await checkpoint.close()
        try:
            with lock_conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
        finally:
            lock_conn.close()

    du_prom = str(du.get("prometheus_textfile_path") or "").strip()
    if du_prom:
        _write_daily_prometheus_textfile(du_prom, cycle_stats, log)

    ok = run_only_pending(config_path, log)
    if not ok:
        _notify_slack(
            (
                "*Encar daily update*: FAILED\n"
                f"new={cycle_stats['new_cars_added']} sold_removed={cycle_stats['sold_cars_removed']} "
                f"pending={cycle_stats['pending_queue_size']}\n"
                "Step `encar_scraper --only-pending` returned non-zero."
            ),
            config,
            log,
        )
    else:
        _notify_slack(
            (
                "*Encar daily update*: OK\n"
                f"new={cycle_stats['new_cars_added']} sold_removed={cycle_stats['sold_cars_removed']} "
                f"pending={cycle_stats['pending_queue_size']}"
            ),
            config,
            log,
        )


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
