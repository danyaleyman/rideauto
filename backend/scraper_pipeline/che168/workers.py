"""Оркестрация Che168: обход брендов/страниц search + воркеры carinfo/spec/recommend/report."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from scraper_pipeline.che168.api_outcome import (
    che168_body_has_listing_signals,
    che168_carinfo_outcome,
    che168_response_suggests_session_refresh,
    che168_search_pagecount,
)
from scraper_pipeline.che168.client import AsyncChe168Client
from scraper_pipeline.che168.parser import (
    _unwrap_layer,
    che168_listing_numeric_id,
    parse_one_che168_car_async,
)
from scraper_pipeline.encar.savers import CarSaver
from scraper_pipeline.checkpoint_pg import CheckpointAsync


def _api_layer_list(payload: Any) -> dict:
    if not isinstance(payload, dict):
        return {}
    for k in ("result", "data"):
        v = payload.get(k)
        if isinstance(v, dict):
            return v
    return payload


def che168_search_items(payload: Any) -> List[dict]:
    layer = _api_layer_list(payload)
    for key in ("carlist", "carList", "list", "List", "rows", "items"):
        v = layer.get(key)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("list", "carlist"):
            v = payload.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def che168_brand_rows(payload: Any) -> List[dict]:
    layer = _api_layer_list(payload)
    for key in ("list", "brandlist", "brands", "BrandList"):
        v = layer.get(key)
        if isinstance(v, list):
            rows = [x for x in v if isinstance(x, dict)]
            return _flatten_brand_letter_groups(rows)
    if isinstance(payload, dict):
        v = payload.get("list")
        if isinstance(v, list):
            rows = [x for x in v if isinstance(x, dict)]
            return _flatten_brand_letter_groups(rows)
    return []


def _flatten_brand_letter_groups(rows: List[dict]) -> List[dict]:
    """API иногда отдаёт [{letter, brand: [{brandid, name}, ...]}]."""
    out: List[dict] = []
    for row in rows:
        nested = row.get("brand")
        if isinstance(nested, list) and nested:
            out.extend(x for x in nested if isinstance(x, dict))
        else:
            out.append(row)
    return out


def che168_brand_id(row: dict) -> Optional[int]:
    for k in ("brandid", "brandId", "brand_id", "BrandID", "bid", "BID", "id", "Id", "ID"):
        n = row.get(k)
        if n is None:
            continue
        s = str(n).strip()
        if s.isdigit():
            return int(s)
        try:
            v = int(float(s))
            if v > 0:
                return v
        except (TypeError, ValueError):
            continue
    return None


def che168_carinfo_body(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}
    layer = _unwrap_layer(raw)
    if che168_listing_numeric_id(layer) or layer.get("price") is not None or layer.get("title"):
        return layer
    return layer


def note_che168_parser_shape_samples(stats: dict, fp: Optional[Dict[str, str]]) -> None:
    if not fp:
        return
    samples: Set[Tuple[str, str]] = stats.setdefault("_che168_shape_samples", set())  # type: ignore[assignment]
    samples.add(
        (
            str(fp.get("list_item_keys_sha1") or ""),
            str(fp.get("carinfo_keys_sha1") or ""),
        )
    )


def _returncode_ok(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return True
    rc = obj.get("returncode", obj.get("returnCode", obj.get("code")))
    if rc is None:
        return True
    try:
        return int(rc) == 0
    except (TypeError, ValueError):
        return str(rc).strip().lower() in ("0", "ok", "success", "")


async def _requeue_after_detail_transient_fail(
    checkpoint: CheckpointAsync,
    external_id: str,
    item_from_list: dict,
) -> None:
    payload = item_from_list if item_from_list else {}
    ij = json.dumps(payload, ensure_ascii=False) if payload else None
    await checkpoint.add_pending(external_id, "che168", ij)


async def list_producer_che168(
    client: AsyncChe168Client,
    checkpoint: CheckpointAsync,
    config: dict,
    stats: dict,
    log: logging.Logger,
    max_cars: int = 0,
    stats_lock: Optional[asyncio.Lock] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    ch = config.get("che168", {}) or {}
    http_cfg = config.get("http", {}) or {}
    pagesize = int(ch.get("search_pagesize", http_cfg.get("list_page_size", 20)))
    sort = int(ch.get("search_sort", 0))
    vehicle_list = int(ch.get("vehicle_list", 0))
    delay_min = float(http_cfg.get("list_page_delay_min", 0.4))
    delay_max = float(http_cfg.get("list_page_delay_max", 1.2))
    stall_limit = int(http_cfg.get("list_stall_pages_limit", 40))
    max_page = int(ch.get("max_pageindex_per_brand", 0) or 0)
    max_fail = max(1, int(http_cfg.get("list_max_fail_streak", 25)))
    brand_parallel = max(1, int(ch.get("list_brand_parallel", 2)))
    brand_fetch_attempts = max(1, int(ch.get("brand_fetch_max_attempts", 5)))

    brand_ids_cfg: List[int] = []
    raw_brands = ch.get("brand_ids")
    if isinstance(raw_brands, list):
        for x in raw_brands:
            try:
                brand_ids_cfg.append(int(x))
            except (TypeError, ValueError):
                continue

    list_fetch_sem = asyncio.Semaphore(max(1, int(http_cfg.get("list_max_parallel", 3))))
    list_stats_lock = asyncio.Lock()
    brand_sem = asyncio.Semaphore(brand_parallel)

    async def _discover_brands() -> List[int]:
        ids = list(brand_ids_cfg)
        if ids:
            return sorted(set(ids))
        for att in range(brand_fetch_attempts):
            async with list_fetch_sem:
                data, status, err = await client.fetch_brands()
            stats["brand_fetch_attempts"] = stats.get("brand_fetch_attempts", 0) + 1
            if status == 200 and data and _returncode_ok(data):
                for row in che168_brand_rows(data):
                    bid = che168_brand_id(row)
                    if bid is not None:
                        ids.append(bid)
                out = sorted(set(ids))
                log.info("Che168 /brand ok attempt=%s brands=%s", att + 1, len(out))
                return out
            log.warning("Che168 /brand fail attempt=%s/%s status=%s err=%s", att + 1, brand_fetch_attempts, status, err)
            await asyncio.sleep(min(90.0, 3.0 * (2**att)))
        log.error("Che168 /brand: попытки исчерпаны — задайте che168.brand_ids в YAML")
        return []

    brand_ids = await _discover_brands()
    if not brand_ids:
        return

    async def _crawl_one_brand(brand_id: int) -> None:
        async with brand_sem:
            if stop_event and stop_event.is_set():
                return
            if max_cars > 0 and stats_lock is not None:
                async with stats_lock:
                    if stats["saved"] >= max_cars:
                        return
            ck_key = f"brand_{brand_id}_page"
            start_page = int(await checkpoint.get_last_offset(ck_key) or 0)
            if start_page < 1:
                start_page = 1
            page = start_page
            stale_full_pages = 0
            fail_streak = 0
            while True:
                if stop_event and stop_event.is_set():
                    log.info("Che168 list producer: stop_event, brand=%s", brand_id)
                    return
                if max_page and page > max_page:
                    log.info("Che168 brand=%s: достигнут max_pageindex=%s", brand_id, max_page)
                    break
                if max_cars > 0 and stats_lock is not None:
                    async with stats_lock:
                        if stats["saved"] >= max_cars:
                            return
                    pend = await checkpoint.pending_count()
                    async with stats_lock:
                        s2 = stats["saved"]
                    if s2 + pend >= max_cars + 3 * pagesize:
                        log.info("Che168: достаточно очереди saved=%s pending=%s", s2, pend)
                        return

                async with list_fetch_sem:
                    data, status, err = await client.fetch_search(
                        brandid=brand_id,
                        pageindex=page,
                        pagesize=pagesize,
                        sort=sort,
                        vehicle_list=vehicle_list,
                    )
                if status != 200 or not data:
                    fail_streak += 1
                    log.warning(
                        "Che168 search brand=%s page=%s status=%s err=%s streak=%s",
                        brand_id,
                        page,
                        status,
                        err,
                        fail_streak,
                    )
                    if fail_streak >= max_fail:
                        log.error("Che168 search brand=%s: слишком много ошибок подряд", brand_id)
                        break
                    cool = min(120.0, 8.0 + 6.0 * min(fail_streak, 15))
                    if status == 407 or status == 429 or status >= 500:
                        await asyncio.sleep(cool)
                    else:
                        await asyncio.sleep(3.0)
                    continue
                fail_streak = 0
                if not _returncode_ok(data):
                    log.warning(
                        "Che168 search brand=%s page=%s returncode err body=%s",
                        brand_id,
                        page,
                        str(data)[:240],
                    )
                    break
                layer = _api_layer_list(data)
                pc_limit = che168_search_pagecount(layer)
                items = che168_search_items(data)
                if not items:
                    stats["che168_search_empty_breaks"] = stats.get("che168_search_empty_breaks", 0) + 1
                    log.info("Che168 search exhausted brand=%s at page=%s", brand_id, page)
                    break

                to_add: List[Tuple[str, str, Any]] = []
                for item in items:
                    ext = che168_listing_numeric_id(item)
                    if not ext:
                        continue
                    if await checkpoint.is_collected(ext):
                        continue
                    to_add.append((ext, "che168", item))
                added = await checkpoint.add_pending_batch(to_add)

                if stall_limit > 0 and added == 0 and len(items) >= max(1, pagesize - 3):
                    stale_full_pages += 1
                    if stale_full_pages >= stall_limit:
                        log.error(
                            "Che168 list stall brand=%s page=%s — %s страниц без новых id",
                            brand_id,
                            page,
                            stall_limit,
                        )
                        break
                else:
                    stale_full_pages = 0

                await checkpoint.set_last_offset(ck_key, page + 1)
                async with list_stats_lock:
                    stats["list_pages"] += 1
                    stats["ids_discovered"] += len(items)
                    stats["ids_queued"] += added
                log.info(
                    "Che168 list brand=%s page=%s pagecount=%s items=%s queued=%s",
                    brand_id,
                    page,
                    pc_limit,
                    len(items),
                    added,
                )
                if pc_limit is not None and page >= pc_limit:
                    log.info("Che168 brand=%s: последняя страница по API pagecount=%s", brand_id, pc_limit)
                    break
                page += 1
                await asyncio.sleep(random.uniform(delay_min, delay_max))

    results = await asyncio.gather(*[_crawl_one_brand(b) for b in brand_ids], return_exceptions=True)
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            log.error("Che168 brand crawl error brand=%s: %s", brand_ids[i] if i < len(brand_ids) else "?", r)


async def detail_worker_che168(
    worker_id: int,
    client: AsyncChe168Client,
    checkpoint: CheckpointAsync,
    saver: CarSaver,
    config: dict,
    queue: asyncio.Queue,
    stats: dict,
    log: logging.Logger,
    max_cars: int = 0,
    stats_lock: Optional[asyncio.Lock] = None,
) -> None:
    sem = asyncio.Semaphore(1)
    ch = config.get("che168", {}) or {}
    assume_wan = bool(ch.get("assume_price_in_wan_yuan", False))
    fetch_recommend = bool(ch.get("fetch_recommend", True))
    fetch_report = bool(ch.get("fetch_report_summary", True))
    taxonomy = ch.get("taxonomy") if isinstance(ch.get("taxonomy"), dict) else None

    def _ep(name: str, ok: bool) -> None:
        stats[f"endpoint_{name}_{'ok' if ok else 'fail'}"] = stats.get(f"endpoint_{name}_{'ok' if ok else 'fail'}", 0) + 1

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            if queue.empty():
                break
            continue
        if item is None:
            break
        if len(item) >= 3:
            external_id, _car_type, item_from_list = item[0], item[1], item[2]
        else:
            external_id, _car_type = item[0], item[1]
            item_from_list = {}
        if not isinstance(item_from_list, dict):
            item_from_list = {}
        if not external_id:
            queue.task_done()
            continue

        max_new = int(config.get("max_new_saves_per_run", 0) or 0)
        if max_new > 0 and stats.get("_save_baseline") is not None:
            if stats["saved"] - stats["_save_baseline"] >= max_new:
                ij = json.dumps(item_from_list, ensure_ascii=False) if item_from_list else None
                await checkpoint.add_pending(str(external_id), "che168", ij)
                queue.task_done()
                continue

        if await checkpoint.is_collected(str(external_id)):
            queue.task_done()
            continue

        if max_cars > 0 and stats_lock is not None:
            async with stats_lock:
                if stats["saved"] >= max_cars:
                    queue.task_done()
                    continue

        detail_wall = float(config.get("http", {}).get("detail_wall_timeout_sec", 90))
        try:
            async with sem:
                raw_info, st_info, _ = await asyncio.wait_for(
                    client.fetch_carinfo(external_id),
                    timeout=detail_wall,
                )
        except asyncio.TimeoutError:
            log.error("Che168 worker %s id=%s carinfo timeout", worker_id, external_id)
            stats["detail_fail"] += 1
            await _requeue_after_detail_transient_fail(checkpoint, str(external_id), item_from_list)
            queue.task_done()
            continue

        outcome = che168_carinfo_outcome(st_info, raw_info)
        if outcome == "retry" and che168_response_suggests_session_refresh(raw_info):
            allow = ch.get("allow_runtime_session_refresh", True) is not False
            if allow:
                min_iv = float(ch.get("session_refresh_min_interval_sec", 90) or 90)
                now = time.monotonic()
                last = float(stats.get("_last_che168_session_refresh_mono") or 0.0)
                if now - last >= min_iv:
                    try:
                        from scraper_pipeline.che168.session_playwright import (
                            apply_playwright_bootstrap_to_config,
                        )

                        log.warning(
                            "Che168 worker %s: сессия/API hint → Playwright bootstrap",
                            worker_id,
                        )
                        await asyncio.to_thread(apply_playwright_bootstrap_to_config, config, log)
                        client.reload_initial_cookies_from_config()
                        stats["_last_che168_session_refresh_mono"] = now
                        stats["session_refreshes"] = stats.get("session_refreshes", 0) + 1
                        raw_info, st_info, _ = await asyncio.wait_for(
                            client.fetch_carinfo(external_id),
                            timeout=detail_wall,
                        )
                        outcome = che168_carinfo_outcome(st_info, raw_info)
                    except ImportError as e:
                        log.error("Che168 session refresh: нужен Playwright — %s", e)
                    except Exception as e:
                        log.error("Che168 session refresh failed: %s", e)
            else:
                stats["detail_session_retry_no_refresh"] = stats.get("detail_session_retry_no_refresh", 0) + 1

        if outcome == "gone":
            await checkpoint.mark_collected(str(external_id))
            stats["detail_gone"] += 1
            log.info(
                "Che168 worker %s infoid=%s listing gone (outcome=gone http=%s)",
                worker_id,
                external_id,
                st_info,
            )
            queue.task_done()
            continue
        if outcome == "retry":
            log.warning(
                "Che168 worker %s infoid=%s carinfo retry http=%s err_meta=%s",
                worker_id,
                external_id,
                st_info,
                (raw_info if isinstance(raw_info, dict) else None),
            )
            stats["detail_fail"] += 1
            await _requeue_after_detail_transient_fail(checkpoint, str(external_id), item_from_list)
            queue.task_done()
            continue

        ci_body = che168_carinfo_body(raw_info)
        if not ci_body or not che168_body_has_listing_signals(ci_body):
            await checkpoint.mark_collected(str(external_id))
            stats["detail_gone"] += 1
            log.info("Che168 worker %s infoid=%s empty carinfo body → gone", worker_id, external_id)
            queue.task_done()
            continue

        _ep("carinfo", True)
        source_meta: Dict[str, Dict[str, Any]] = {
            "carinfo": {"status": st_info, "ok": True, "latency_ms": None, "error": None},
        }

        specid = ci_body.get("specid") or ci_body.get("specId")
        dealerid = ci_body.get("dealerid") or ci_body.get("dealerId")
        paramkey = ci_body.get("paramkey") or ci_body.get("paramKey") or ""
        if isinstance(paramkey, str):
            paramkey = paramkey.strip()
        else:
            paramkey = str(paramkey or "")

        tasks: List[Tuple[str, Any]] = []
        if specid is not None and str(specid).strip():
            sid = str(specid).strip()
            tasks.append(("specparam", client.fetch_specparam(sid)))
            tasks.append(("specconfig", client.fetch_specconfig(sid)))
        if fetch_recommend:
            tasks.append(("recommend", client.fetch_recommend(infoid=external_id, pageindex=1, pagesize=20)))
        if fetch_report and dealerid is not None and str(dealerid).strip() and paramkey:
            tasks.append(
                ("report_summary", client.fetch_report_summary(str(dealerid).strip(), paramkey)),
            )

        results: Dict[str, Any] = {}
        if tasks:
            extras_wall = float(config.get("http", {}).get("detail_extras_wall_timeout_sec", 120))
            try:
                done = await asyncio.wait_for(
                    asyncio.gather(*[c for _, c in tasks], return_exceptions=True),
                    timeout=extras_wall,
                )
            except asyncio.TimeoutError:
                log.error("Che168 worker %s id=%s extras timeout", worker_id, external_id)
                stats["extras_timeout"] = stats.get("extras_timeout", 0) + 1
                done = [asyncio.TimeoutError() for _ in tasks]
            for i, (name, _) in enumerate(tasks):
                if i >= len(done):
                    continue
                d = done[i]
                if isinstance(d, Exception):
                    results[name] = None
                    source_meta[name] = {"status": 0, "ok": False, "error": str(d)[:200]}
                    _ep(name, False)
                else:
                    payload, st, _err = d
                    ok = st == 200 and isinstance(payload, dict) and _returncode_ok(payload)
                    results[name] = payload if ok else None
                    source_meta[name] = {"status": st, "ok": ok, "error": None if ok else "non_200_or_api"}
                    _ep(name, ok)

        cookie_hints: Dict[str, str] = {}
        ar = client.get_initial_cookie("area")
        ios = client.get_initial_cookie("is_overseas")
        if ar:
            cookie_hints["area"] = ar
        if ios:
            cookie_hints["is_overseas"] = ios

        parse_wall = float(config.get("http", {}).get("parse_wall_timeout_sec", 120))
        try:
            car = await asyncio.wait_for(
                parse_one_che168_car_async(
                    external_id=str(external_id),
                    list_item=item_from_list,
                    carinfo=ci_body,
                    specparam=results.get("specparam"),
                    specconfig=results.get("specconfig"),
                    recommend=results.get("recommend"),
                    report_summary=results.get("report_summary"),
                    assume_price_wan_yuan=assume_wan,
                    source_meta=source_meta,
                    taxonomy=taxonomy,
                    session_cookie_hints=cookie_hints if cookie_hints else None,
                    listing_cluster=ch.get("listing_cluster")
                    if isinstance(ch.get("listing_cluster"), dict)
                    else None,
                ),
                timeout=parse_wall,
            )
        except asyncio.TimeoutError:
            log.error("Che168 worker %s id=%s parse timeout", worker_id, external_id)
            stats["parse_fail"] += 1
            stats["processed"] += 1
            queue.task_done()
            continue

        car_id = f"che168-{external_id}"
        if car:
            note_che168_parser_shape_samples(stats, (car.get("data") or {}).get("parser_shape_fingerprints"))
            _d = car.get("data") or {}
            _tel = _d.get("che168_cluster_telemetry") if isinstance(_d.get("che168_cluster_telemetry"), dict) else {}
            for _k, _v in _tel.items():
                if isinstance(_v, int):
                    sk = f"che168_telemetry_{_k}"
                    stats[sk] = stats.get(sk, 0) + _v
            _cm = _d.get("che168_listing_cluster_method")
            if _cm:
                sk2 = f"che168_cluster_method_{_cm}"
                stats[sk2] = stats.get(sk2, 0) + 1
            did_save = False
            if max_cars > 0 and stats_lock is not None:
                async with stats_lock:
                    if stats["saved"] < max_cars:
                        await saver.save_car(car, car_id)
                        await checkpoint.mark_collected(str(external_id))
                        stats["saved"] += 1
                        did_save = True
            else:
                await saver.save_car(car, car_id)
                await checkpoint.mark_collected(str(external_id))
                stats["saved"] += 1
                did_save = True
            if did_save and stats["saved"] % 100 == 0:
                log.info("Che168 worker %s saved total=%s", worker_id, stats["saved"])
            if max_cars > 0 and not did_save:
                stats["parse_fail"] += 1
        else:
            stats["parse_fail"] += 1
        stats["processed"] += 1
        queue.task_done()
