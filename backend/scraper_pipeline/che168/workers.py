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
from scraper_pipeline.che168.image_downloader import AsyncImageDownloader
from scraper_pipeline.che168.parser import (
    che168_collect_api_layer_photo_urls,
    che168_listing_numeric_id,
    extract_gallery_urls_from_detail_html,
    merge_che168_api_carinfo_envelope,
    merge_che168_image_url_lists,
    parse_one_che168_car_async,
)
from scraper_pipeline.che168.runtime_stats import Che168Stats
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
    layer = merge_che168_api_carinfo_envelope(raw)
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


def _coerce_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        # Accept numbers and numeric strings.
        s = str(v).strip()
        if not s:
            return None
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _parse_range_pairs(raw_pairs: Any, *, open_ended_max_zero: bool = True) -> List[Tuple[int, Optional[int]]]:
    """
    Parse config like [[min,max], ...] into [(min, max_or_None), ...].
    If max==0 and open_ended_max_zero is True => treat as "no upper bound".
    """
    out: List[Tuple[int, Optional[int]]] = []
    if not isinstance(raw_pairs, list):
        return out
    for pair in raw_pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        a = _coerce_int(pair[0])
        b = _coerce_int(pair[1])
        if a is None:
            continue
        if b is None:
            continue
        if open_ended_max_zero and b == 0:
            out.append((a, None))
        else:
            out.append((a, b))
    return out


def build_segments(seg_cfg: dict) -> List[dict]:
    """
    Build Che168 search segments for segmentation workaround.

    Supported strategies:
    - price_x_year: cartesian product of price_segments x year_segments
    """
    if not isinstance(seg_cfg, dict) or not seg_cfg.get("enabled"):
        return [{}]

    strategy = str(seg_cfg.get("strategy") or "price_x_year").strip().lower()
    max_segments = max(1, int(seg_cfg.get("max_segments_per_brand", 100) or 100))

    price_pairs = _parse_range_pairs(seg_cfg.get("price_segments") or [], open_ended_max_zero=True)
    year_pairs = _parse_range_pairs(seg_cfg.get("year_segments") or [], open_ended_max_zero=False)

    segments: List[dict] = []
    if strategy == "price_x_year":
        if not price_pairs or not year_pairs:
            return [{}]
        for p_min, p_max in price_pairs:
            for y_min, y_max in year_pairs:
                if p_max is None:
                    p_key = f"price_{p_min}_plus"
                else:
                    p_key = f"price_{p_min}_{p_max}"
                if y_max is None:
                    y_key = f"year_{y_min}_plus"
                else:
                    y_key = f"year_{y_min}_{y_max}"
                segments.append(
                    {
                        "price_min": p_min,
                        "price_max": p_max,
                        "year_min": y_min,
                        "year_max": y_max,
                        "key": f"{p_key}_{y_key}",
                    }
                )
    else:
        # Unknown strategy => fallback to non-segmented mode.
        return [{}]

    if not segments:
        return [{}]
    return segments[:max_segments]


async def detect_search_pagination_mode(
    client: AsyncChe168Client,
    *,
    preferred_mode: str,
    probe_brandid: int,
    pagesize: int,
    sort: int,
    vehicle_list: int,
    probe_segment: Optional[dict],
    log: logging.Logger,
) -> str:
    """
    Detect effective pagination mode.

    - preferred_mode=pageindex|offset: return as-is.
    - preferred_mode=auto: probe offset/limit support, fallback to pageindex.
    """
    mode = str(preferred_mode or "pageindex").strip().lower()
    if mode in {"pageindex", "offset"}:
        return mode

    seg = probe_segment or {}
    kwargs = {
        "price_min": seg.get("price_min"),
        "price_max": seg.get("price_max"),
        "year_min": seg.get("year_min"),
        "year_max": seg.get("year_max"),
    }

    # Probe offset mode: compare offset=0 vs offset=pagesize.
    d0, s0, e0 = await client.fetch_search_with_offset(
        brandid=probe_brandid,
        offset=0,
        limit=pagesize,
        sort=sort,
        vehicle_list=vehicle_list,
        **kwargs,
    )
    d1, s1, e1 = await client.fetch_search_with_offset(
        brandid=probe_brandid,
        offset=pagesize,
        limit=pagesize,
        sort=sort,
        vehicle_list=vehicle_list,
        **kwargs,
    )

    if s0 == 200 and s1 == 200 and d0 and d1 and _returncode_ok(d0) and _returncode_ok(d1):
        i0 = che168_search_items(d0)
        i1 = che168_search_items(d1)
        if i0 and i1:
            # If result sets differ, offset likely works.
            ids0 = {che168_listing_numeric_id(x) for x in i0}
            ids1 = {che168_listing_numeric_id(x) for x in i1}
            ids0.discard(None)
            ids1.discard(None)
            if ids0 and ids1 and ids0 != ids1:
                log.info(
                    "Che168 pagination auto-detect: offset mode selected (brand=%s probe ids differ)",
                    probe_brandid,
                )
                return "offset"
        # If both pages return items but identical IDs, treat as unsupported offset.
        log.info(
            "Che168 pagination auto-detect: offset probe ambiguous/identical, fallback to pageindex "
            "(brand=%s items0=%s items1=%s)",
            probe_brandid,
            len(i0),
            len(i1),
        )
    else:
        log.info(
            "Che168 pagination auto-detect: offset probe failed, fallback to pageindex "
            "(brand=%s s0=%s s1=%s e0=%s e1=%s)",
            probe_brandid,
            s0,
            s1,
            e0,
            e1,
        )

    return "pageindex"


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

    seg_cfg = ch.get("segmentation", {}) if isinstance(ch.get("segmentation"), dict) else {}
    seg_enabled = bool(seg_cfg.get("enabled"))
    pagination_mode = str(ch.get("search_pagination_mode") or "pageindex").strip().lower()
    segment_checkpoints = bool(seg_cfg.get("segment_checkpoints", True))
    probe_segment = build_segments(seg_cfg)[0] if seg_enabled else {}
    pagination_mode = await detect_search_pagination_mode(
        client,
        preferred_mode=pagination_mode,
        probe_brandid=brand_ids[0],
        pagesize=pagesize,
        sort=sort,
        vehicle_list=vehicle_list,
        probe_segment=probe_segment if isinstance(probe_segment, dict) else {},
        log=log,
    )

    if not seg_enabled:
        async def _crawl_one_brand(brand_id: int) -> None:
            async with brand_sem:
                if stop_event and stop_event.is_set():
                    return
                if max_cars > 0 and stats_lock is not None:
                    async with stats_lock:
                        if stats["saved"] >= max_cars:
                            return
                ck_key = f"brand_{brand_id}_{'offset' if pagination_mode == 'offset' else 'page'}"
                if pagination_mode == "offset":
                    start_off = int(await checkpoint.get_last_offset(ck_key) or 0)
                    if start_off < 0:
                        start_off = 0
                    off = start_off
                else:
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
                    if pagination_mode == "offset":
                        if max_page and off >= (max_page + 1) * pagesize:
                            log.info("Che168 brand=%s: reached max_offset (max_page=%s)", brand_id, max_page)
                            break
                    else:
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
                        if pagination_mode == "offset":
                            data, status, err = await client.fetch_search_with_offset(
                                brandid=brand_id,
                                offset=off,
                                limit=pagesize,
                                sort=sort,
                                vehicle_list=vehicle_list,
                            )
                        else:
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
                            "Che168 search brand=%s page=%s off=%s status=%s err=%s streak=%s",
                            brand_id,
                            locals().get("page"),
                            locals().get("off"),
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
                            locals().get("page"),
                            str(data)[:240],
                        )
                        break
                    layer = _api_layer_list(data)
                    pc_limit = che168_search_pagecount(layer)
                    items = che168_search_items(data)
                    if not items:
                        stats["che168_search_empty_breaks"] = stats.get("che168_search_empty_breaks", 0) + 1
                        log.info(
                            "Che168 search exhausted brand=%s at page=%s off=%s",
                            brand_id,
                            locals().get("page"),
                            locals().get("off"),
                        )
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
                            locals().get("page"),
                                stall_limit,
                            )
                            break
                    else:
                        stale_full_pages = 0

                    if pagination_mode == "offset":
                        await checkpoint.set_last_offset(ck_key, off + pagesize)
                    else:
                        await checkpoint.set_last_offset(ck_key, page + 1)
                    async with list_stats_lock:
                        stats["list_pages"] += 1
                        stats["ids_discovered"] += len(items)
                        stats["ids_queued"] += added
                    log.info(
                        "Che168 list brand=%s page=%s off=%s pagecount=%s items=%s queued=%s",
                        brand_id,
                        locals().get("page"),
                        locals().get("off"),
                        pc_limit,
                        len(items),
                        added,
                    )
                    if pagination_mode != "offset" and pc_limit is not None and page >= pc_limit:
                        log.info("Che168 brand=%s: последняя страница по API pagecount=%s", brand_id, pc_limit)
                        break
                    if pagination_mode == "offset":
                        off += pagesize
                    else:
                        page += 1
                    await asyncio.sleep(random.uniform(delay_min, delay_max))

        results = await asyncio.gather(*[_crawl_one_brand(b) for b in brand_ids], return_exceptions=True)
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                log.error(
                    "Che168 brand crawl error brand=%s: %s",
                    brand_ids[i] if i < len(brand_ids) else "?",
                    r,
                )
        return

    # Segmented mode: split large API search into many smaller filtered segments.
    segments = build_segments(seg_cfg)
    parallel_segments = max(1, int(seg_cfg.get("parallel_segments", 4) or 4))
    segment_sem = asyncio.Semaphore(parallel_segments)
    log.info(
        "Che168 segmentation: enabled=%s strategy=%s segments=%s pagination_mode=%s",
        seg_enabled,
        seg_cfg.get("strategy"),
        len(segments),
        pagination_mode,
    )

    async def _crawl_brand_segment(brand_id: int, segment: dict) -> None:
        async with segment_sem:
            if stop_event and stop_event.is_set():
                return
            if max_cars > 0 and stats_lock is not None:
                async with stats_lock:
                    if stats["saved"] >= max_cars:
                        return

            segment_key = str(segment.get("key") or "default").strip()
            ck_key = f"segment_{brand_id}_{segment_key}_{'offset' if pagination_mode=='offset' else 'page'}"
            if not segment_checkpoints:
                ck_key = f"brand_{brand_id}_page"

            # pageindex mode stores "next pageindex" (>=1); offset mode stores raw offset.
            if pagination_mode == "offset":
                start_off = int(await checkpoint.get_last_offset(ck_key) or 0)
                if start_off < 0:
                    start_off = 0
                off = start_off
            else:
                start_page = int(await checkpoint.get_last_offset(ck_key) or 0)
                if start_page < 1:
                    start_page = 1
                page = start_page

            stale_full_pages = 0
            fail_streak = 0
            while True:
                if stop_event and stop_event.is_set():
                    log.info(
                        "Che168 list producer: stop_event, brand=%s segment=%s",
                        brand_id,
                        segment_key,
                    )
                    return

                if pagination_mode == "offset":
                    # If max_page is configured, convert pages->offset.
                    if max_page and off >= (max_page + 1) * pagesize:
                        log.info(
                            "Che168 brand=%s segment=%s: reached max_offset (max_page=%s pagesize=%s)",
                            brand_id,
                            segment_key,
                            max_page,
                            pagesize,
                        )
                        break
                else:
                    if max_page and page > max_page:
                        log.info("Che168 brand=%s: reached max_pageindex=%s", brand_id, max_page)
                        break

                if max_cars > 0 and stats_lock is not None:
                    async with stats_lock:
                        if stats["saved"] >= max_cars:
                            return
                    pend = await checkpoint.pending_count()
                    async with stats_lock:
                        s2 = stats["saved"]
                    if s2 + pend >= max_cars + 3 * pagesize:
                        log.info("Che168: enough queue saved=%s pending=%s", s2, pend)
                        return

                async with list_fetch_sem:
                    if pagination_mode == "offset":
                        data, status, err = await client.fetch_search_with_offset(
                            brandid=brand_id,
                            offset=off,
                            limit=pagesize,
                            sort=sort,
                            vehicle_list=vehicle_list,
                            price_min=segment.get("price_min"),
                            price_max=segment.get("price_max"),
                            year_min=segment.get("year_min"),
                            year_max=segment.get("year_max"),
                        )
                    else:
                        data, status, err = await client.fetch_search(
                            brandid=brand_id,
                            pageindex=page,
                            pagesize=pagesize,
                            sort=sort,
                            vehicle_list=vehicle_list,
                            price_min=segment.get("price_min"),
                            price_max=segment.get("price_max"),
                            year_min=segment.get("year_min"),
                            year_max=segment.get("year_max"),
                        )

                if status != 200 or not data:
                    fail_streak += 1
                    log.warning(
                        "Che168 search brand=%s seg=%s page=%s off=%s status=%s err=%s streak=%s",
                        brand_id,
                        segment_key,
                        locals().get("page"),
                        locals().get("off"),
                        status,
                        err,
                        fail_streak,
                    )
                    if fail_streak >= max_fail:
                        log.error(
                            "Che168 search brand=%s segment=%s: too many errors in a row",
                            brand_id,
                            segment_key,
                        )
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
                        "Che168 search brand=%s seg=%s: non-ok returncode page=%s body=%s",
                        brand_id,
                        segment_key,
                        locals().get("page"),
                        str(data)[:240],
                    )
                    break

                layer = _api_layer_list(data)
                pc_limit = che168_search_pagecount(layer)
                items = che168_search_items(data)
                if not items:
                    stats["che168_search_empty_breaks"] = stats.get("che168_search_empty_breaks", 0) + 1
                    log.info(
                        "Che168 segment exhausted brand=%s seg=%s at page=%s off=%s",
                        brand_id,
                        segment_key,
                        locals().get("page"),
                        locals().get("off"),
                    )
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
                            "Che168 list stall brand=%s seg=%s page=%s off=%s — %s pages without new ids",
                            brand_id,
                            segment_key,
                            locals().get("page"),
                            locals().get("off"),
                            stall_limit,
                        )
                        break
                else:
                    stale_full_pages = 0

                if pagination_mode == "offset":
                    await checkpoint.set_last_offset(ck_key, off + pagesize)
                else:
                    await checkpoint.set_last_offset(ck_key, page + 1)

                async with list_stats_lock:
                    stats["list_pages"] += 1
                    stats["ids_discovered"] += len(items)
                    stats["ids_queued"] += added

                log.info(
                    "Che168 list brand=%s seg=%s page=%s off=%s pagecount=%s items=%s queued=%s",
                    brand_id,
                    segment_key,
                    locals().get("page"),
                    locals().get("off"),
                    pc_limit,
                    len(items),
                    added,
                )

                # pc_limit is meaningful mainly for pageindex mode.
                if pagination_mode != "offset" and pc_limit is not None and page >= pc_limit:
                    log.info(
                        "Che168 brand=%s seg=%s: last page by API pagecount=%s",
                        brand_id,
                        segment_key,
                        pc_limit,
                    )
                    break

                if pagination_mode == "offset":
                    off += pagesize
                else:
                    page += 1

                await asyncio.sleep(random.uniform(delay_min, delay_max))

    tasks = []
    for brand_id in brand_ids:
        for segment in segments:
            tasks.append(_crawl_brand_segment(brand_id, segment))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            # tasks order is brand x segment; we just log generic info.
            log.error("Che168 segment crawl error task_index=%s: %s", i, r)


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
    mon_cfg = ch.get("monitoring") if isinstance(ch.get("monitoring"), dict) else {}
    batch_cfg = ch.get("batch") if isinstance(ch.get("batch"), dict) else {}
    image_downloader = AsyncImageDownloader(config, log)
    image_download_enabled = bool(((ch.get("image_download") or {}) if isinstance(ch.get("image_download"), dict) else {}).get("enabled", False))
    rt_stats = Che168Stats(enabled=bool(mon_cfg.get("enable_parser_stats", True)))
    batch_insert_size = max(1, int(batch_cfg.get("insert_size", 1000) or 1000))
    batch_flush_interval_sec = float(batch_cfg.get("flush_interval_sec", 5.0) or 5.0)
    save_buffer: List[Tuple[dict, str, str]] = []
    last_flush_mono = time.monotonic()
    assume_wan = bool(ch.get("assume_price_in_wan_yuan", False))
    fetch_recommend = bool(ch.get("fetch_recommend", True))
    fetch_report = bool(ch.get("fetch_report_summary", True))
    taxonomy = ch.get("taxonomy") if isinstance(ch.get("taxonomy"), dict) else None

    def _ep(name: str, ok: bool) -> None:
        stats[f"endpoint_{name}_{'ok' if ok else 'fail'}"] = stats.get(f"endpoint_{name}_{'ok' if ok else 'fail'}", 0) + 1

    async def _flush_save_buffer(force: bool = False) -> None:
        nonlocal last_flush_mono
        if max_cars > 0:
            return
        if not save_buffer:
            return
        if not force and len(save_buffer) < batch_insert_size and (time.monotonic() - last_flush_mono) < batch_flush_interval_sec:
            return
        payload = [(car, car_id) for car, car_id, _ext_id in save_buffer]
        saved_n = await saver.bulk_save(payload, batch_size=batch_insert_size)
        for _car, _car_id, ext_id in save_buffer:
            await checkpoint.mark_collected(str(ext_id))
        stats["saved"] += int(saved_n)
        save_buffer.clear()
        last_flush_mono = time.monotonic()

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            # Important for long-running segmented crawl:
            # queue may be temporarily empty between refill/listing waves.
            # Exiting worker here can leave producer alive with no consumers.
            continue
        if item is None:
            await _flush_save_buffer(force=True)
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

        if bool(ch.get("fetch_detail_gallery_html", True)):
            html, st_h, err_h = await client.fetch_global_detail_html(external_id)
            source_meta["detail_page"] = {
                "status": int(st_h),
                "ok": st_h == 200 and bool(html),
                "error": None if st_h == 200 else str(err_h or "")[:220],
            }
            if st_h == 200 and html:
                page_urls = extract_gallery_urls_from_detail_html(html)
                if page_urls:
                    api_urls = che168_collect_api_layer_photo_urls(ci_body)
                    ci_body["images"] = merge_che168_image_url_lists(page_urls, api_urls)
                    if len(page_urls) >= 2:
                        stats["detail_html_gallery_ge2"] = stats.get("detail_html_gallery_ge2", 0) + 1

        specid = ci_body.get("specid") or ci_body.get("specId")
        dealerid = ci_body.get("dealerid") or ci_body.get("dealerId")
        paramkey = ci_body.get("paramkey") or ci_body.get("paramKey") or ""
        if (specid is None or not str(specid).strip()) and isinstance(raw_info, dict):
            raw_result = raw_info.get("result")
            if isinstance(raw_result, dict):
                restored = raw_result.get("specid") or raw_result.get("specId")
                if restored is not None and str(restored).strip():
                    specid = restored
                    log.info("Che168 worker %s: restored specid=%s for id=%s", worker_id, restored, external_id)
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
            if image_download_enabled and isinstance(_d.get("images"), list) and _d.get("images"):
                dl = await image_downloader.download_many(car_id=car_id, urls=_d.get("images") or [])
                _d["image_assets"] = dl.get("assets") or []
                _d["image_assets_status"] = {
                    "enabled": bool(dl.get("enabled")),
                    "attempted": int(dl.get("attempted", 0) or 0),
                    "downloaded": int(dl.get("downloaded", 0) or 0),
                    "duplicates": int(dl.get("duplicates", 0) or 0),
                }
                stats["image_download_attempted"] = stats.get("image_download_attempted", 0) + int(
                    dl.get("attempted", 0) or 0
                )
                stats["image_downloaded"] = stats.get("image_downloaded", 0) + int(dl.get("downloaded", 0) or 0)
                stats["image_download_duplicates"] = stats.get("image_download_duplicates", 0) + int(
                    dl.get("duplicates", 0) or 0
                )
                rt_stats.add_photos(
                    downloaded=int(dl.get("downloaded", 0) or 0),
                    failed=max(0, int(dl.get("attempted", 0) or 0) - int(dl.get("downloaded", 0) or 0)),
                )
            if results.get("specparam") is not None:
                rt_stats.mark_with_spec()
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
                save_buffer.append((car, car_id, str(external_id)))
                await _flush_save_buffer(force=False)
                did_save = True
            if did_save and stats["saved"] % 100 == 0:
                log.info("Che168 worker %s saved total=%s", worker_id, stats["saved"])
            if max_cars > 0 and not did_save:
                stats["parse_fail"] += 1
        else:
            stats["parse_fail"] += 1
        stats["processed"] += 1
        if rt_stats.enabled:
            snap = rt_stats.snapshot()
            stats["photos_downloaded"] = snap["photos_downloaded"]
            stats["photos_failed"] = snap["photos_failed"]
            stats["cars_with_spec"] = snap["cars_with_spec"]
        queue.task_done()
    await _flush_save_buffer(force=True)
