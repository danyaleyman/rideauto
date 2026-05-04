"""
Che168 Global: асинхронный скрейпер (search по брендам → carinfo + spec + опции → Postgres).

Отдельный чекпоинт scope (по умолчанию `che168`), не смешивается с Encar.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

from encar_scraper import (
    _flush_queue_to_pending,
    _postgres_dsn_for_checkpoint,
    _run_postgres_catalog_sync,
    load_config,
)
from scraper_pipeline.checkpoint_pg import CheckpointAsync
from scraper_pipeline.che168.client import AsyncChe168Client
from scraper_pipeline.che168.taxonomy_sync import (
    merge_che168_taxonomy_with_brand_api,
    sync_che168_series_taxonomy,
)
from scraper_pipeline.che168.workers import (
    _returncode_ok,
    detail_worker_che168,
    list_producer_che168,
)
from scraper_pipeline.encar.savers import build_car_saver


class _FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


def _repo_root_for_logging(cfg: dict) -> Path:
    raw_cfg = cfg.get("_resolved_config_path")
    start = Path(str(raw_cfg)).resolve().parent if raw_cfg else Path.cwd()
    for cand in [start, *start.parents]:
        if (cand / "backend" / "che168_scraper.py").is_file():
            return cand
    return start


def setup_logging(cfg: dict) -> logging.Logger:
    log_cfg = cfg.get("logging", {})
    level = getattr(logging, str(log_cfg.get("level", "INFO")).upper(), logging.INFO)
    fmt = log_cfg.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handlers: List[logging.Handler] = []
    if log_cfg.get("console", True):
        h = _FlushingStreamHandler()
        h.setFormatter(logging.Formatter(fmt))
        handlers.append(h)
    log_file = log_cfg.get("file")
    if log_file:
        cfg_base = _repo_root_for_logging(cfg)
        lp = Path(log_file)
        if not lp.is_absolute():
            lp = cfg_base / lp
        try:
            lp.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(lp, encoding="utf-8")
            fh.setFormatter(logging.Formatter(fmt))
            handlers.append(fh)
        except OSError as e:
            sys.stderr.write(f"che168_scraper: cannot open log file {lp}: {e}; using console only\n")
    logging.basicConfig(level=level, format=fmt, handlers=handlers or [_FlushingStreamHandler()])
    return logging.getLogger("che168_scraper")


def _new_saves_cap_reached(stats: dict, config: dict) -> bool:
    max_new = int(config.get("max_new_saves_per_run", 0) or 0)
    if max_new <= 0:
        return False
    b = stats.get("_save_baseline")
    if b is None:
        return False
    return (stats["saved"] - b) >= max_new


async def run_scraper(
    config_path: str = "che168_scraper.yaml",
    max_cars_override: Optional[int] = None,
    only_pending: bool = False,
) -> None:
    config = load_config(config_path)
    _dev = (os.environ.get("CHE168_DEVICE_ID") or os.environ.get("CHE168_DEVICEID") or "").strip()
    if _dev:
        config.setdefault("che168", {})["deviceid"] = _dev
    log = setup_logging(config)
    _bootstrap_env = str(os.environ.get("CHE168_PLAYWRIGHT_BOOTSTRAP", "")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if _bootstrap_env or bool((config.get("che168") or {}).get("playwright_bootstrap_on_start")):
        try:
            from scraper_pipeline.che168.session_playwright import apply_playwright_bootstrap_to_config

            log.info("Che168: Playwright bootstrap сессии…")
            await asyncio.to_thread(apply_playwright_bootstrap_to_config, config, log)
        except ImportError as e:
            log.error(
                "Playwright не установлен: pip install playwright && playwright install chromium — %s",
                e,
            )
            raise
    log.info("Старт Che168 Global scraper%s", " (only-pending)" if only_pending else "")

    checkpoint_cfg = config.get("checkpoint", {}) or {}
    max_pending = int(checkpoint_cfg.get("max_pending_ids", 500000))
    scope = str(checkpoint_cfg.get("scope", "che168")).strip() or "che168"
    cp_dsn = _postgres_dsn_for_checkpoint(config)
    if not cp_dsn:
        raise ValueError("Che168 checkpoint: нужен DATABASE_URL или storage.postgres.dsn")

    checkpoint = CheckpointAsync(dsn=cp_dsn, scope=scope, max_pending=max_pending)
    await checkpoint.connect()
    log.info("Che168 checkpoint scope=%s", scope)

    saver, backend = None, ""
    try:
        saver, backend = build_car_saver(config)
    except Exception:
        await checkpoint.close()
        raise

    concurrency = int(config.get("http", {}).get("concurrency", 6) or 6)
    _loop = asyncio.get_running_loop()
    _n_cpu = os.cpu_count() or 4
    http_cfg = config.get("http", {}) or {}
    _tp_cap = http_cfg.get("thread_pool_max_workers")
    if _tp_cap is not None and int(_tp_cap) > 0:
        _tp_workers = int(_tp_cap)
    else:
        _tp_workers = max(32, concurrency * 6, _n_cpu * 4)
    _loop.set_default_executor(
        concurrent.futures.ThreadPoolExecutor(max_workers=_tp_workers, thread_name_prefix="ch168_scraper")
    )

    stats: dict[str, Any] = {
        "list_pages": 0,
        "ids_discovered": 0,
        "ids_queued": 0,
        "processed": 0,
        "saved": 0,
        "detail_fail": 0,
        "detail_gone": 0,
        "parse_fail": 0,
        "extras_timeout": 0,
        "brand_fetch_attempts": 0,
        "session_refreshes": 0,
        "che168_search_empty_breaks": 0,
        "detail_session_retry_no_refresh": 0,
        "_che168_shape_samples": set(),
        "_last_che168_session_refresh_mono": 0.0,
    }
    initial_saved = await saver.count_saved()
    if initial_saved:
        stats["saved"] = initial_saved
        log.info("В БД уже %s строк cars — лимит max_cars учитывает это", initial_saved)

    max_new = int(config.get("max_new_saves_per_run", 0) or 0)
    if max_new > 0:
        stats["_save_baseline"] = initial_saved
        log.info("Лимит прогона: max_new_saves_per_run=%s (база saved=%s)", max_new, initial_saved)
    else:
        stats["_save_baseline"] = None

    queue: asyncio.Queue = asyncio.Queue(maxsize=concurrency * 4)
    stats_lock = asyncio.Lock()
    start_time = time.time()
    refill_done = False
    stop_ev = asyncio.Event()

    def _on_signal(*_args: Any) -> None:
        log.warning("Che168: получен сигнал остановки — list producer завершит текущие страницы")
        stop_ev.set()

    try:
        signal.signal(signal.SIGINT, _on_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _on_signal)
    except ValueError:
        pass

    try:
        max_cars = int(max_cars_override if max_cars_override is not None else (config.get("max_cars", 0) or 0))
        if max_cars > 0:
            log.info("Ограничение max_cars=%s", max_cars)

        async with AsyncChe168Client(config, log) as client:
            ch0 = config.setdefault("che168", {})
            if ch0.get("taxonomy_sync_from_brand_api", True):
                raw_b, st_b, err_b = await client.fetch_brands()
                if st_b == 200 and raw_b and _returncode_ok(raw_b):
                    yaml_tax = dict(ch0.get("taxonomy")) if isinstance(ch0.get("taxonomy"), dict) else {}
                    ch0["taxonomy"] = merge_che168_taxonomy_with_brand_api(raw_b, yaml_tax)
                    t = ch0["taxonomy"]
                    log.info(
                        "Che168 taxonomy: синхронизация /brand — brand_by_id=%s mark_aliases=%s",
                        len(t.get("brand_by_id") or {}),
                        len(t.get("mark_aliases") or {}),
                    )
                else:
                    log.warning("Che168 taxonomy: пропуск /brand status=%s err=%s", st_b, err_b)

            await sync_che168_series_taxonomy(client, config, log)

            workers = [
                asyncio.create_task(
                    detail_worker_che168(
                        i,
                        client,
                        checkpoint,
                        saver,
                        config,
                        queue,
                        stats,
                        log,
                        max_cars=max_cars,
                        stats_lock=stats_lock if max_cars > 0 else None,
                    )
                )
                for i in range(concurrency)
            ]

            async def log_stats():
                first_wait = True
                while not refill_done:
                    await asyncio.sleep(15 if first_wait else 60)
                    first_wait = False
                    p = await checkpoint.pending_count()
                    elapsed_sec = time.time() - start_time
                    shape_n = len(stats.get("_che168_shape_samples") or ())
                    shape_warn = ""
                    if shape_n > 2:
                        shape_warn = f" che168_shape_variants={shape_n}"
                    log.info(
                        "Stats: elapsed_sec=%.0f processed=%s saved=%s detail_gone=%s detail_fail=%s "
                        "parse_fail=%s session_refreshes=%s search_empty_breaks=%s pending=%s queue=%s%s",
                        elapsed_sec,
                        stats["processed"],
                        stats["saved"],
                        stats["detail_gone"],
                        stats["detail_fail"],
                        stats["parse_fail"],
                        stats.get("session_refreshes", 0),
                        stats.get("che168_search_empty_breaks", 0),
                        p,
                        queue.qsize(),
                        shape_warn,
                    )

            stats_task = asyncio.create_task(log_stats())

            pending_limit = max(concurrency * 8, 64)
            if int(config.get("max_new_saves_per_run", 0) or 0) > 0:
                cap_nv = int(config.get("max_new_saves_per_run", 0) or 0)
                pending_limit = min(pending_limit, max(concurrency + cap_nv, cap_nv * 6, 16))

            pending = await checkpoint.pop_pending_batch(pending_limit)
            for rec in pending:
                await queue.put(rec if len(rec) == 3 else (rec[0], rec[1], None))
            if pending:
                log.info("Resumed pending: %s", len(pending))

            if only_pending:
                producer = asyncio.create_task(asyncio.sleep(0))
            else:
                producer = asyncio.create_task(
                    list_producer_che168(
                        client,
                        checkpoint,
                        config,
                        stats,
                        log,
                        max_cars=max_cars,
                        stats_lock=stats_lock if max_cars > 0 else None,
                        stop_event=stop_ev,
                    )
                )

            async def refill_queue():
                nonlocal refill_done
                while True:
                    if _new_saves_cap_reached(stats, config):
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        break
                    await asyncio.sleep(15)
                    if max_cars > 0 and stats["saved"] >= max_cars:
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        break
                    if queue.qsize() > concurrency * 3:
                        continue
                    batch = await checkpoint.pop_pending_batch(100)
                    pending_left = await checkpoint.pending_count()
                    for it in batch:
                        await queue.put(it)
                    if producer.done() and not batch and pending_left == 0:
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        break

            refill_task = asyncio.create_task(refill_queue())
            await producer

            if only_pending:
                pass
            else:
                for _ in range(1000):
                    if _new_saves_cap_reached(stats, config):
                        break
                    batch = await checkpoint.pop_pending_batch(100)
                    pending_left = await checkpoint.pending_count()
                    for it in batch:
                        await queue.put(it)
                    if not batch and pending_left == 0:
                        break
                    await asyncio.sleep(0.3)

            if _new_saves_cap_reached(stats, config):
                refill_done = True
                refill_task.cancel()
                try:
                    await refill_task
                except asyncio.CancelledError:
                    pass
                for _ in workers:
                    await queue.put(None)

            await asyncio.gather(*workers)
            refill_done = True
            stats_task.cancel()
            try:
                await stats_task
            except asyncio.CancelledError:
                pass
            refill_task.cancel()
            try:
                await refill_task
            except asyncio.CancelledError:
                pass

    finally:
        if int(config.get("max_new_saves_per_run", 0) or 0) > 0:
            try:
                await _flush_queue_to_pending(checkpoint, queue, log)
            except Exception as e:
                log.warning("Не удалось вернуть хвост очереди в pending: %s", e)
        await checkpoint.close()
        if saver is not None:
            saver.close()

    ep_summary = " ".join(f"{k}={v}" for k, v in sorted(stats.items()) if k.startswith("endpoint_"))
    log.info(
        "Che168 scraper finished list_pages=%s saved=%s detail_gone=%s detail_fail=%s parse_fail=%s brand_fetch_attempts=%s%s",
        stats["list_pages"],
        stats["saved"],
        stats["detail_gone"],
        stats["detail_fail"],
        stats["parse_fail"],
        stats.get("brand_fetch_attempts", 0),
        f" | {ep_summary}" if ep_summary else "",
    )

    tp = (os.environ.get("CHE168_PROMETHEUS_TEXTFILE") or "").strip()
    if not tp:
        tp = str((config.get("che168") or {}).get("prometheus_textfile_path") or "").strip()
    if tp:
        try:
            from scraper_pipeline.che168.scraper_prometheus import (
                write_che168_scraper_prometheus_textfile,
            )

            write_che168_scraper_prometheus_textfile(tp, stats)
        except Exception as e:
            log.warning("Che168 Prometheus textfile: %s", e)

    if backend == "postgres":
        if os.environ.get("SKIP_FRONTEND_EXPORT", "").strip().lower() in ("1", "true", "yes", "on"):
            log.info("postgres_catalog_sync пропущен (SKIP_FRONTEND_EXPORT)")
        else:
            _run_postgres_catalog_sync(config_path, config, log)


def main() -> None:
    import argparse

    _repo_root = Path(__file__).resolve().parent.parent
    _default_config = _repo_root / "che168_scraper.yaml"
    p = argparse.ArgumentParser(description="Che168 Global async scraper")
    p.add_argument("--config", default=str(_default_config), help="YAML конфиг (по умолчанию корень репозитория)")
    p.add_argument("--max-cars", type=int, default=None, metavar="N")
    p.add_argument("--only-pending", action="store_true")
    args = p.parse_args()
    asyncio.run(
        run_scraper(
            config_path=args.config,
            max_cars_override=args.max_cars,
            only_pending=args.only_pending,
        )
    )


if __name__ == "__main__":
    main()
