"""
Production Encar.com scraper: async pipeline (fetcher → parser → saver),
чекпоинт в PostgreSQL, экспоненциальный backoff в HTTP-клиенте.

Архитектура: ``backend/scraper_pipeline/`` (retry, checkpoint, encar client/parser/savers/workers).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import yaml

from parser_full import EncarFullParser
from scraper_pipeline.checkpoint_pg import CheckpointAsync
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


def _new_saves_cap_reached(stats: dict, config: dict) -> bool:
    max_new = int(config.get("max_new_saves_per_run", 0) or 0)
    if max_new <= 0:
        return False
    b = stats.get("_save_baseline")
    if b is None:
        return False
    return (stats["saved"] - b) >= max_new


async def _flush_queue_to_pending(
    checkpoint: CheckpointAsync,
    queue: asyncio.Queue,
    log: logging.Logger,
) -> None:
    """Вернуть необработанные задачи из asyncio.Queue в scraper_pending_ids (при раннем стопе)."""
    n = 0
    while True:
        try:
            item = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if item is None:
            continue
        if len(item) >= 3:
            car_id, car_type, payload = item[0], item[1], item[2]
        else:
            car_id, car_type = item[0], item[1]
            payload = None
        ij = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else None
        await checkpoint.add_pending(str(car_id), str(car_type), ij)
        n += 1
    if n:
        log.info("Очередь скрейпера: возвращено в pending записей: %s", n)


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
    checkpoint = CheckpointAsync(dsn=cp_dsn, scope=scope, max_pending=max_pending)
    await checkpoint.connect()
    log.info("Чекпоинт Encar: отдельный поток БД (CheckpointAsync)")
    saver, backend = None, ""
    try:
        saver, backend = build_car_saver(config)
    except Exception:
        await checkpoint.close()
        raise

    car_types = config.get("car_types", ["for", "kor"])
    concurrency = int(config.get("http", {}).get("concurrency", 8) or 8)

    # Парсер + save_car используют default executor; чекпоинт — только CheckpointAsync (свой 1 поток).
    _loop = asyncio.get_running_loop()
    _n_cpu = os.cpu_count() or 4
    _tp_workers = max(32, concurrency * 6, _n_cpu * 4)
    _loop.set_default_executor(
        concurrent.futures.ThreadPoolExecutor(max_workers=_tp_workers, thread_name_prefix="enc_scraper")
    )
    log.info("Пул потоков asyncio (парсер/save): max_workers=%s", _tp_workers)
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
    max_new = int(config.get("max_new_saves_per_run", 0) or 0)
    if max_new > 0:
        stats["_save_baseline"] = initial_saved
        log.info(
            "Лимит прогона: max_new_saves_per_run=%s (новых INSERT в cars за этот запуск; база saved=%s)",
            max_new,
            initial_saved,
        )
    else:
        stats["_save_baseline"] = None

    queue: asyncio.Queue = asyncio.Queue(maxsize=concurrency * 4)
    log.info("Инициализация EncarFullParser…")
    parser = EncarFullParser()
    stats_lock = asyncio.Lock()
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

            async def log_stats():
                # Запускаем до enqueue: иначе при залипании на queue.put тишина в journal до часов.
                first_wait = True
                while not refill_done:
                    await asyncio.sleep(15 if first_wait else 60)
                    first_wait = False
                    p = await checkpoint.pending_count()
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

            pending_limit = max(concurrency * 8, 64)
            cap_nv = int(config.get("max_new_saves_per_run", 0) or 0)
            if cap_nv > 0:
                # Иначе из pending берутся сотни самых старых id — воркеры могут залипнуть на них до тестовых новых.
                pending_limit = min(pending_limit, max(concurrency + cap_nv, cap_nv * 6, 16))
                log.info(
                    "Тест max_new_saves_per_run=%s: лимит выборки pending снижен до %s",
                    cap_nv,
                    pending_limit,
                )
            log.info("Чтение pending из checkpoint (лимит %s)…", pending_limit)
            t_pop0 = time.monotonic()
            pending = await checkpoint.pop_pending_batch(pending_limit)
            log.info(
                "Checkpoint pop_pending_batch: %s строк за %.2fs",
                len(pending),
                time.monotonic() - t_pop0,
            )
            if pending:
                log.info("Checkpoint pending выгружен: %s записей (enqueue в очередь…)", len(pending))
            enqueue_log_every = max(8, min(concurrency * 4, 32))
            for i, rec in enumerate(pending, start=1):
                if i == 1 or i % enqueue_log_every == 0:
                    log.info("Checkpoint enqueue: кладём %s/%s (queue_size≈%s)", i, len(pending), queue.qsize())
                await queue.put(rec if len(rec) == 3 else (rec[0], rec[1], None))
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
                    if _new_saves_cap_reached(stats, config):
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        log.info(
                            "Refill stopping: max_new_saves_per_run (saved=%s, лимит +%s)",
                            stats["saved"],
                            int(config.get("max_new_saves_per_run", 0) or 0),
                        )
                        break
                    await asyncio.sleep(15)
                    if max_cars > 0 and stats["saved"] >= max_cars:
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        log.info("Refill stopping: max_cars=%s reached (saved=%s)", max_cars, stats["saved"])
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

            log.info("Ожидание list producer…")
            await producer
            try:
                for _refill_round in range(1000):
                    if _new_saves_cap_reached(stats, config):
                        log.info("Дозагрузка pending остановлена: max_new_saves_per_run")
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
        if int(config.get("max_new_saves_per_run", 0) or 0) > 0:
            try:
                await _flush_queue_to_pending(checkpoint, queue, log)
            except Exception as e:
                log.warning("Не удалось вернуть хвост очереди в pending: %s", e)
        await checkpoint.close()
        if saver is not None:
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
