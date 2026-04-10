"""Оркестрация: list producer (fetch) + detail workers (fetch → parse → save)."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any, List, Optional, Tuple

from parser_full import EncarFullParser

from scraper_pipeline.checkpoint_pg import Checkpoint
from scraper_pipeline.encar.client import AsyncEncarClient
from scraper_pipeline.encar.parser import parse_one_car_async
from scraper_pipeline.encar.savers import CarSaver


async def _list_one_variant(
    client: AsyncEncarClient,
    checkpoint: Checkpoint,
    checkpoint_lock: asyncio.Lock,
    list_fetch_sem: asyncio.Semaphore,
    list_stats_lock: asyncio.Lock,
    car_type: str,
    type_label: str,
    vidx: int,
    n_variants: int,
    q_suffix: str,
    page_size: int,
    max_offset: int,
    delay_min: float,
    delay_max: float,
    stall_limit: int,
    stall_jump_pages: int,
    stall_jump_max: int,
    stats: dict,
    log: logging.Logger,
    max_cars: int,
    stats_lock: Optional[asyncio.Lock],
) -> None:
    if isinstance(q_suffix, str) and q_suffix.strip() == "":
        q_suffix = ""
    if n_variants == 1 or (vidx == 0 and not q_suffix):
        ck_key = car_type
    else:
        ck_key = f"{car_type}_v{vidx}"
    log.info(
        "List phase type=%s (%s) variant %s/%s q_suffix=%r checkpoint_key=%s",
        car_type,
        type_label,
        vidx + 1,
        n_variants,
        q_suffix or "(base)",
        ck_key,
    )
    async with checkpoint_lock:
        offset = int(checkpoint.get_last_offset(ck_key))
    list_fail_streak = 0
    stale_full_pages = 0
    stall_jumps_used = 0
    while offset < max_offset:
        if max_cars > 0 and stats_lock is not None:
            async with stats_lock:
                saved_now = stats["saved"]
            if saved_now >= max_cars:
                log.info("List producer stopping: max_cars=%s (уже в БД/сессии)", max_cars)
                break
            pend = await asyncio.to_thread(checkpoint.pending_count)
            async with stats_lock:
                saved2 = stats["saved"]
            if saved2 + pend >= max_cars + 3 * page_size:
                log.info(
                    "List producer stopping: достаточно очереди (saved=%s pending=%s max_cars=%s)",
                    saved2,
                    pend,
                    max_cars,
                )
                break
        async with list_fetch_sem:
            data, status, err = await client.fetch_list_page(
                offset, page_size, car_type, q_suffix=q_suffix or ""
            )
        if status != 200 or not data:
            log.warning(
                "List page failed car_type=%s variant=%s offset=%s status=%s err=%s",
                car_type,
                ck_key,
                offset,
                status,
                err,
            )
            if status in (407, 429) or (status >= 500 and offset > 0):
                list_fail_streak += 1
                if list_fail_streak > 25:
                    log.error(
                        "List: too many failures at offset=%s, stopping list for %s variant=%s",
                        offset,
                        car_type,
                        ck_key,
                    )
                    break
                if status == 407:
                    cool = min(180.0, 8.0 + 7.0 * min(list_fail_streak, 20))
                    log.info("List: пауза %.0f с после 407 (серия %s)", cool, list_fail_streak)
                    await asyncio.sleep(cool)
                else:
                    await asyncio.sleep(60)
                continue
            break
        list_fail_streak = 0
        items = data.get("SearchResults") or []
        api_count = data.get("Count") or data.get("TotalCount") or data.get("totalCount")
        if not items:
            log.info(
                "List exhausted car_type=%s variant=%s at offset=%s api_count=%s",
                car_type,
                ck_key,
                offset,
                api_count,
            )
            break
        do_stall_jump = False
        do_break_stall = False
        log_offset = offset
        n_items = len(items)
        to_add: List[Tuple[str, str, Any]] = []
        for item in items:
            car_id = str(item.get("Id", ""))
            if not car_id:
                continue
            if await asyncio.to_thread(checkpoint.is_collected, car_id):
                continue
            to_add.append((car_id, car_type, item))
        async with checkpoint_lock:
            added = checkpoint.add_pending_batch(to_add)
            if stall_limit > 0 and added == 0 and len(items) >= max(1, page_size - 5):
                stale_full_pages += 1
                if stale_full_pages >= stall_limit:
                    if stall_jump_max > 0 and stall_jumps_used < stall_jump_max:
                        skip = stall_jump_pages * page_size
                        offset += skip
                        checkpoint.set_last_offset(ck_key, offset)
                        stale_full_pages = 0
                        stall_jumps_used += 1
                        do_stall_jump = True
                    else:
                        do_break_stall = True
            else:
                stale_full_pages = 0
            if not do_stall_jump and not do_break_stall:
                checkpoint.set_last_offset(ck_key, offset + page_size)
                offset += page_size
        if do_break_stall:
            log.error(
                "List stall: car_type=%s variant=%s offset=%s — %s full pages with nothing new queued; stop",
                car_type,
                ck_key,
                log_offset,
                stall_limit,
            )
            break
        if do_stall_jump:
            log.warning(
                "List stall jump: type=%s variant=%s +%s results (~%s pages), "
                "offset now=%s (jump %s/%s); продолжаем обход",
                car_type,
                ck_key,
                stall_jump_pages * page_size,
                stall_jump_pages,
                offset,
                stall_jumps_used,
                stall_jump_max,
            )
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            continue
        async with list_stats_lock:
            stats["list_pages"] += 1
            stats["ids_discovered"] += n_items
            stats["ids_queued"] += added
        log.info(
            "List car_type=%s variant=%s offset=%s items=%s queued=%s api_count=%s",
            car_type,
            ck_key,
            log_offset,
            n_items,
            added,
            api_count,
        )
        await asyncio.sleep(random.uniform(delay_min, delay_max))


async def list_producer(
    client: AsyncEncarClient,
    checkpoint: Checkpoint,
    checkpoint_lock: asyncio.Lock,
    config: dict,
    car_types: List[str],
    stats: dict,
    log: logging.Logger,
    max_cars: int = 0,
    stats_lock: Optional[asyncio.Lock] = None,
) -> None:
    http_cfg = config.get("http", {})
    page_size = http_cfg.get("list_page_size", 100)
    raw_max = http_cfg.get("max_list_offset", 10000)
    hard_cap = int(http_cfg.get("list_offset_hard_cap", 10_000_000))
    try:
        max_offset = hard_cap if raw_max in (None, 0, "0") else int(raw_max)
    except (TypeError, ValueError):
        max_offset = hard_cap
    delay_min = float(http_cfg.get("list_page_delay_min", 0.5))
    delay_max = float(http_cfg.get("list_page_delay_max", 1.5))
    stall_limit = int(http_cfg.get("list_stall_pages_limit", 50))
    stall_jump_pages = max(1, int(http_cfg.get("list_stall_offset_jump_pages", 150)))
    stall_jump_max = max(0, int(http_cfg.get("list_stall_jump_max", 40)))
    variants = http_cfg.get("list_q_suffixes")
    if not isinstance(variants, list) or not variants:
        variants = [""]
    parallel = bool(http_cfg.get("list_parallel_variants", False))
    list_max_parallel = max(1, int(http_cfg.get("list_max_parallel", 4)))
    list_fetch_sem = asyncio.Semaphore(list_max_parallel)
    list_stats_lock = asyncio.Lock()

    work: List[Tuple[str, str, int, str]] = []
    for car_type in car_types:
        if max_cars > 0 and stats_lock is not None:
            async with stats_lock:
                if stats["saved"] >= max_cars:
                    log.info("List producer stopping: max_cars=%s reached", max_cars)
                    break
        type_label = "import" if car_type == "for" else "domestic"
        for vidx, q_suffix in enumerate(variants):
            if max_cars > 0 and stats_lock is not None:
                async with stats_lock:
                    if stats["saved"] >= max_cars:
                        break
            qs = q_suffix if isinstance(q_suffix, str) else ""
            work.append((car_type, type_label, vidx, qs))

    async def _run_slice(car_type: str, type_label: str, vidx: int, qs: str) -> None:
        await _list_one_variant(
            client,
            checkpoint,
            checkpoint_lock,
            list_fetch_sem,
            list_stats_lock,
            car_type,
            type_label,
            vidx,
            len(variants),
            qs,
            page_size,
            max_offset,
            delay_min,
            delay_max,
            stall_limit,
            stall_jump_pages,
            stall_jump_max,
            stats,
            log,
            max_cars,
            stats_lock,
        )

    if parallel and len(work) > 1:
        log.info(
            "List producer: параллельно %s срезов, до %s одновременных запросов к list API",
            len(work),
            list_max_parallel,
        )
        await asyncio.gather(*[_run_slice(ct, tl, vi, qs) for ct, tl, vi, qs in work])
    else:
        for ct, tl, vi, qs in work:
            await _run_slice(ct, tl, vi, qs)
    log.info("List producer finished for car_types=%s", car_types)


async def detail_worker(
    worker_id: int,
    client: AsyncEncarClient,
    checkpoint: Checkpoint,
    saver: CarSaver,
    parser: EncarFullParser,
    _config: dict,
    queue: asyncio.Queue,
    stats: dict,
    log: logging.Logger,
    max_cars: int = 0,
    stats_lock: Optional[asyncio.Lock] = None,
) -> None:
    sem = asyncio.Semaphore(1)
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            if queue.empty():
                break
            continue
        if item is None:
            break
        if len(item) == 3:
            car_id, car_type, item_from_list = item
            if item_from_list is None:
                item_from_list = {}
        else:
            car_id, _car_type = item[0], item[1]
            item_from_list = item[2] if len(item) > 2 else {}
        if not item_from_list:
            item_from_list = {"Id": car_id}
        max_new = int(_config.get("max_new_saves_per_run", 0) or 0)
        if max_new > 0 and stats.get("_save_baseline") is not None:
            if stats["saved"] - stats["_save_baseline"] >= max_new:
                ij = json.dumps(item_from_list, ensure_ascii=False) if item_from_list else None
                await asyncio.to_thread(checkpoint.add_pending, car_id, car_type, ij)
                queue.task_done()
                continue
        if await asyncio.to_thread(checkpoint.is_collected, car_id):
            queue.task_done()
            continue
        if _config.get("http", {}).get("log_detail_starts"):
            log.info("Worker %s detail car_id=%s", worker_id, car_id)
        if max_cars > 0 and stats_lock is not None:
            async with stats_lock:
                if stats["saved"] >= max_cars:
                    queue.task_done()
                    continue
        detail_wall = float(_config.get("http", {}).get("detail_wall_timeout_sec", 90))
        log.debug("Worker %s detail begin car_id=%s", worker_id, car_id)
        try:
            async with sem:
                detail, d_status, _ = await asyncio.wait_for(
                    client.fetch_vehicle_detail(car_id),
                    timeout=detail_wall,
                )
        except asyncio.TimeoutError:
            log.error(
                "Worker %s car_id=%s: vehicle detail >%.0fs (сеть/прокси) — отпускаем слот очереди",
                worker_id,
                car_id,
                detail_wall,
            )
            stats["detail_fail"] += 1
            queue.task_done()
            continue
        if d_status != 200 or not detail:
            if d_status in (404, 410):
                await asyncio.to_thread(checkpoint.mark_collected, car_id)
                stats["detail_gone"] += 1
                log.info(
                    "Worker %s car_id=%s detail %s — снято/продано, помечаем collected (не в БД)",
                    worker_id,
                    car_id,
                    d_status,
                )
            else:
                log.warning("Worker %s car_id=%s detail failed status=%s", worker_id, car_id, d_status)
                stats["detail_fail"] += 1
            queue.task_done()
            continue
        plate = detail.get("vehicleNo") if detail else None
        seller_id = None
        sep_item = detail.get("item")
        if isinstance(sep_item, list) and sep_item:
            sep_item = sep_item[0]
        if isinstance(sep_item, dict) and sep_item.get("Separation"):
            seller_id = (sep_item.get("Separation") or [None])[0]
        if not seller_id and item_from_list.get("Separation"):
            seller_id = (item_from_list.get("Separation") or [None])[0]
        has_diag = False
        if detail:
            adv = detail.get("advertisement") or {}
            if adv.get("hasUnderBodyPhoto"):
                has_diag = True
            for p in detail.get("photos") or []:
                if p.get("type") == "DIAG2":
                    has_diag = True
                    break
        tasks = []
        if plate:
            tasks.append(("record", client.fetch_record(car_id, plate)))
        if has_diag:
            tasks.append(("diagnosis", client.fetch_diagnosis(car_id)))
        tasks.append(("inspection", client.fetch_inspection(car_id)))
        tasks.append(("sellingpoint", client.fetch_sellingpoint(car_id)))
        if seller_id:
            tasks.append(("user", client.fetch_user(seller_id)))
        results = {}
        if tasks:
            extras_wall = float(_config.get("http", {}).get("detail_extras_wall_timeout_sec", 120))
            try:
                done = await asyncio.wait_for(
                    asyncio.gather(*[c for _, c in tasks], return_exceptions=True),
                    timeout=extras_wall,
                )
            except asyncio.TimeoutError:
                log.error(
                    "Worker %s car_id=%s: record/inspection/… >%.0fs — продолжаем с тем что есть",
                    worker_id,
                    car_id,
                    extras_wall,
                )
                done = [asyncio.TimeoutError() for _ in tasks]
            for i, (name, _) in enumerate(tasks):
                if i >= len(done):
                    continue
                d = done[i]
                if isinstance(d, Exception):
                    log.debug("Worker %s car_id=%s %s: %s", worker_id, car_id, name, d)
                    results[name] = None
                else:
                    data, status, _ = d
                    results[name] = data if status == 200 else None
        record = results.get("record")
        diagnosis = results.get("diagnosis")
        inspection = results.get("inspection")
        if not inspection and detail:
            inspection = (detail.get("condition") or {}).get("inspection")
        sellingpoint = results.get("sellingpoint")
        user_info = results.get("user")
        parse_wall = float(_config.get("http", {}).get("parse_wall_timeout_sec", 120))
        try:
            car = await asyncio.wait_for(
                parse_one_car_async(
                    parser,
                    car_id,
                    item_from_list or {"Id": car_id},
                    detail,
                    diagnosis,
                    record,
                    inspection,
                    sellingpoint,
                    user_info,
                ),
                timeout=parse_wall,
            )
        except asyncio.TimeoutError:
            log.error(
                "Worker %s car_id=%s: parse CPU/normalize >%.0fs — parse_fail",
                worker_id,
                car_id,
                parse_wall,
            )
            stats["parse_fail"] += 1
            stats["processed"] += 1
            queue.task_done()
            continue
        if car:
            did_save = False
            if max_cars > 0 and stats_lock is not None:
                async with stats_lock:
                    if stats["saved"] < max_cars:
                        await saver.save_car(car, car_id)
                        await asyncio.to_thread(checkpoint.mark_collected, car_id)
                        stats["saved"] += 1
                        did_save = True
            else:
                await saver.save_car(car, car_id)
                await asyncio.to_thread(checkpoint.mark_collected, car_id)
                stats["saved"] += 1
                did_save = True
            if did_save and stats["saved"] % 100 == 0:
                log.info("Worker %s saved car_id=%s total=%s", worker_id, car_id, stats["saved"])
            if max_cars > 0 and not did_save:
                stats["parse_fail"] += 1
        else:
            stats["parse_fail"] += 1
        stats["processed"] += 1
        queue.task_done()
