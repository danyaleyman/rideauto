"""
Production Encar.com scraper: async pipeline (fetcher → parser → saver),
чекпоинт в PostgreSQL, экспоненциальный backoff в HTTP-клиенте.

Архитектура: ``backend/scraper_pipeline/`` (retry, checkpoint, encar client/parser/savers/workers).
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import yaml

from parser_full import EncarFullParser
from scraper_pipeline.checkpoint_pg import Checkpoint
from scraper_pipeline.encar.client import AsyncEncarClient
from scraper_pipeline.encar.savers import build_car_saver
from scraper_pipeline.encar.workers import detail_worker, list_producer


def _postgres_dsn_for_checkpoint(config: dict) -> str:
    cp = config.get("checkpoint", {}) or {}
    pg_cp = cp.get("postgres")
    if isinstance(pg_cp, dict):
        d = str(pg_cp.get("dsn") or "").strip()
        if d:
            return d
    storage_cfg = config.get("storage", {}) or {}
    d = str((storage_cfg.get("postgres") or {}).get("dsn") or "").strip()
    if d:
        return d
    return (os.environ.get("DATABASE_URL") or "").strip()


def load_config(config_path: str = "scraper_config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    config["_resolved_config_path"] = str(path.resolve())
    for key, value in os.environ.items():
        if not key.startswith("SCRAPER_"):
            continue
        parts = key[8:].lower().split("_")
        if len(parts) < 2:
            continue
        section = parts[0]
        subkey = "_".join(parts[1:])
        if section not in config:
            config[section] = {}
        try:
            if isinstance(value, str) and value.isdigit():
                config[section][subkey] = int(value)
            elif value.lower() in ("true", "false"):
                config[section][subkey] = value.lower() == "true"
            else:
                config[section][subkey] = value
        except Exception:
            config[section][subkey] = value
    return config


class _FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


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
        raw_cfg = cfg.get("_resolved_config_path")
        cfg_base = Path(str(raw_cfg)).resolve().parent if raw_cfg else Path.cwd()
        lp = Path(log_file)
        if not lp.is_absolute():
            lp = cfg_base / lp
        try:
            lp.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(lp, encoding="utf-8")
            fh.setFormatter(logging.Formatter(fmt))
            handlers.append(fh)
        except OSError as e:
            sys.stderr.write(f"encar_scraper: cannot open log file {lp}: {e}; using console only\n")
    logging.basicConfig(level=level, format=fmt, handlers=handlers or [_FlushingStreamHandler()])
    return logging.getLogger("encar_scraper")


async def run_scraper(
    config_path: str = "scraper_config.yaml",
    max_cars_override: Optional[int] = None,
    only_pending: bool = False,
) -> None:
    config = load_config(config_path)
    log = setup_logging(config)
    log.info("Starting Encar scraper%s", " (only-pending)" if only_pending else "")
    checkpoint_cfg = config.get("checkpoint", {})
    max_pending = int(checkpoint_cfg.get("max_pending_ids", 500000))
    scope = str(checkpoint_cfg.get("scope", "encar")).strip() or "encar"
    cp_dsn = _postgres_dsn_for_checkpoint(config)
    if not cp_dsn:
        raise ValueError("Чекпоинт Encar: нужен DATABASE_URL или storage.postgres.dsn / checkpoint.postgres.dsn")
    checkpoint = Checkpoint(dsn=cp_dsn, scope=scope, max_pending=max_pending)
    checkpoint.connect()

    saver, backend = build_car_saver(config)
    car_types = config.get("car_types", ["for", "kor"])
    concurrency = config.get("http", {}).get("concurrency", 8)
    stats = {
        "list_pages": 0,
        "ids_discovered": 0,
        "ids_queued": 0,
        "processed": 0,
        "saved": 0,
        "detail_fail": 0,
        "detail_gone": 0,
        "parse_fail": 0,
    }
    initial_saved = await saver.count_saved()
    if initial_saved:
        stats["saved"] = initial_saved
        log.info("Уже в хранилище %s записей — лимит max_cars считается с учётом них", initial_saved)

    queue: asyncio.Queue = asyncio.Queue(maxsize=concurrency * 4)
    log.info("Инициализация EncarFullParser…")
    parser = EncarFullParser()
    stats_lock = asyncio.Lock()
    checkpoint_lock = asyncio.Lock()
    start_time = time.time()
    refill_done = False

    try:
        max_cars = int(max_cars_override if max_cars_override is not None else (config.get("max_cars", 0) or 0))
        if max_cars > 0:
            log.info("Run limited to max_cars=%s", max_cars)

        log.info(
            "Запуск HTTP-клиента (async list + workers); прокси async=%s URL",
            len(config.get("proxy", {}).get("urls") or []) if config.get("proxy", {}).get("enabled") else 0,
        )
        async with AsyncEncarClient(config, log) as client:
            workers = [
                asyncio.create_task(
                    detail_worker(
                        i,
                        client,
                        checkpoint,
                        checkpoint_lock,
                        saver,
                        parser,
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
            pending_limit = max(concurrency * 8, 64)
            log.info("Чтение pending из checkpoint (лимит %s)…", pending_limit)
            async with checkpoint_lock:
                pending = checkpoint.pop_pending_batch(limit=pending_limit)
            if pending:
                log.info("Checkpoint pending выгружен: %s записей (enqueue в очередь…)", len(pending))
            for i, rec in enumerate(pending, start=1):
                await queue.put(rec if len(rec) == 3 else (rec[0], rec[1], None))
                if i % max(concurrency * 8, 64) == 0:
                    log.info("Checkpoint enqueue progress: %s/%s", i, len(pending))
            if pending:
                log.info("Resumed with %s pending IDs from checkpoint", len(pending))
            else:
                log.info("Checkpoint pending на старте: 0 (list producer заполнит очередь)")

            if only_pending:
                producer = asyncio.create_task(asyncio.sleep(0))
            else:
                producer = asyncio.create_task(
                    list_producer(
                        client,
                        checkpoint,
                        checkpoint_lock,
                        config,
                        car_types,
                        stats,
                        log,
                        max_cars=max_cars,
                        stats_lock=stats_lock if max_cars > 0 else None,
                    )
                )

            async def refill_queue():
                nonlocal refill_done
                while True:
                    await asyncio.sleep(15)
                    if max_cars > 0 and stats["saved"] >= max_cars:
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        log.info("Refill stopping: max_cars=%s reached (saved=%s)", max_cars, stats["saved"])
                        break
                    if queue.qsize() > concurrency * 3:
                        continue
                    async with checkpoint_lock:
                        batch = checkpoint.pop_pending_batch(limit=100)
                        pending_left = checkpoint.pending_count()
                    for it in batch:
                        await queue.put(it)
                    if producer.done() and not batch and pending_left == 0:
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        break

            refill_task = asyncio.create_task(refill_queue())

            async def log_stats():
                while not refill_done:
                    await asyncio.sleep(60)
                    async with checkpoint_lock:
                        p = checkpoint.pending_count()
                    log.info(
                        "Stats: processed=%s saved=%s detail_gone=%s detail_fail=%s parse_fail=%s pending=%s queue_size=%s",
                        stats["processed"],
                        stats["saved"],
                        stats["detail_gone"],
                        stats["detail_fail"],
                        stats["parse_fail"],
                        p,
                        queue.qsize(),
                    )

            stats_task = asyncio.create_task(log_stats())
            log.info("Ожидание list producer…")
            await producer
            try:
                for _refill_round in range(1000):
                    async with checkpoint_lock:
                        batch = checkpoint.pop_pending_batch(limit=100)
                        pending_left = checkpoint.pending_count()
                    for it in batch:
                        await queue.put(it)
                    if not batch and pending_left == 0:
                        break
                    await asyncio.sleep(0.3)
                await asyncio.gather(*workers)
            except asyncio.CancelledError:
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
                for _ in workers:
                    try:
                        queue.put_nowait(None)
                    except asyncio.QueueFull:
                        break
                await asyncio.gather(*workers, return_exceptions=True)
                raise
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
        checkpoint.close()
        saver.close()

    elapsed = time.time() - start_time
    log.info(
        "Scraper finished. list_pages=%s ids_discovered=%s ids_queued=%s processed=%s saved=%s detail_gone=%s detail_fail=%s parse_fail=%s elapsed=%.1fs",
        stats["list_pages"],
        stats["ids_discovered"],
        stats["ids_queued"],
        stats["processed"],
        stats["saved"],
        stats["detail_gone"],
        stats["detail_fail"],
        stats["parse_fail"],
        elapsed,
    )
    try:
        power_stats = parser.get_power_stats()
        log.info(
            "Мощность: с мощностью=%s без мощности=%s",
            power_stats.get("with_power", 0),
            power_stats.get("without_power", 0),
        )
    except Exception:
        pass

    if backend == "postgres":
        if os.environ.get("SKIP_FRONTEND_EXPORT", "").strip().lower() in ("1", "true", "yes", "on"):
            log.info(
                "Синхронизация Postgres пропущена (SKIP_FRONTEND_EXPORT). "
                "Запустите: python backend/postgres_catalog_sync.py --config …"
            )
        else:
            _run_postgres_catalog_sync(config_path, log)


def _run_postgres_catalog_sync(config_path: str, log: logging.Logger) -> None:
    """После scraper с storage.backend=postgres: цены в БД + опционально Meilisearch (см. postgres_catalog_sync.py)."""
    if os.environ.get("SKIP_POSTGRES_CATALOG_SYNC", "").strip().lower() in ("1", "true", "yes", "on"):
        log.info("postgres_catalog_sync пропущен (SKIP_POSTGRES_CATALOG_SYNC)")
        return
    backend_dir = Path(__file__).resolve().parent
    sync_script = backend_dir / "postgres_catalog_sync.py"
    if not sync_script.is_file():
        log.warning("postgres_catalog_sync.py не найден: %s", sync_script)
        return
    cmd = [
        os.environ.get("PYTHON", sys.executable),
        str(sync_script),
        "--config",
        str(Path(config_path).resolve()),
    ]
    if os.environ.get("WRITE_STATIC_CATALOG", "").strip().lower() in ("1", "true", "yes", "on"):
        cmd.extend(["--write-static-json", "--static-gzip", "--static-chunk-size", "5000"])
    if os.environ.get("SKIP_LEARN_ENGINE_MAP", "").strip().lower() not in ("1", "true", "yes", "on"):
        cmd.append("--learn-engine-map")
    try:
        r = subprocess.run(cmd, cwd=str(backend_dir))
        if r.returncode == 0:
            log.info("Синхронизация каталога Postgres (цены/Meili) выполнена")
        else:
            log.warning("postgres_catalog_sync завершился с кодом %s", r.returncode)
    except Exception as e:
        log.warning("Ошибка postgres_catalog_sync: %s", e)


def main() -> None:
    import argparse

    _repo_root = Path(__file__).resolve().parent.parent
    _default_config = _repo_root / "scraper_config.yaml"
    p = argparse.ArgumentParser(description="Encar async scraper: list pages + detail workers")
    p.add_argument("--config", default=str(_default_config), help="Config YAML path (default: repo root)")
    p.add_argument("--max-cars", type=int, default=None, metavar="N", help="Stop after N cars saved (overrides config)")
    p.add_argument("--only-pending", action="store_true", help="Only process pending IDs from checkpoint (no list producer)")
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
