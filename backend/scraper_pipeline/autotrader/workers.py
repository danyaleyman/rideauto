"""List + detail workers for Autotrader USA."""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path
from typing import Any, Dict, Optional, Set

from scraper_pipeline.autotrader.client import AsyncAutotraderClient
from scraper_pipeline.autotrader.parser import (
    car_id_for_listing,
    normalize_listing,
    parse_srp_page,
    parse_vdp_page,
)
from scraper_pipeline.autotrader.runtime_stats import AutotraderStats
from scraper_pipeline.encar.savers import CarSaver

log = logging.getLogger(__name__)


async def run_autotrader_offline_ingest(
    saver: CarSaver,
    *,
    srp_html: str,
    vdp_by_id: Optional[Dict[str, str]] = None,
    max_cars: int = 0,
    logger: Optional[logging.Logger] = None,
    stats: Optional[AutotraderStats] = None,
) -> AutotraderStats:
    """Parse local SRP (+ optional VDP HTML map) and save without network."""
    lg = logger or log
    st = stats or AutotraderStats()
    vdp_by_id = vdp_by_id or {}

    parsed = parse_srp_page(srp_html)
    if not parsed.get("ok"):
        raise RuntimeError("offline SRP parse failed")
    st.list_pages_ok += 1

    active_ids = list(parsed["active_ids"])
    inventory = parsed["inventory"]
    lg.info(
        "Autotrader offline SRP ids=%s inventory=%s vdp_files=%s",
        len(active_ids),
        len(inventory),
        len(vdp_by_id),
    )

    for lid in active_ids:
        if max_cars > 0 and st.saved >= max_cars:
            break
        st.listings_seen += 1
        card = inventory.get(lid)
        depth = "srp"
        listing = card
        vhtml = vdp_by_id.get(lid)
        if vhtml:
            try:
                vparsed = parse_vdp_page(vhtml, listing_id=lid)
                if vparsed.get("ok") and vparsed.get("listing"):
                    listing = vparsed["listing"]
                    depth = "vdp"
                    st.details_ok += 1
                else:
                    st.details_fail += 1
            except Exception as e:
                st.details_fail += 1
                st.errors.append(f"vdp {lid}: {e}")
                lg.warning("offline VDP %s failed: %s", lid, e)

        if not isinstance(listing, dict):
            st.skipped += 1
            continue
        try:
            car = normalize_listing(listing, listing_id=lid, depth=depth)
            cid = car_id_for_listing(lid)
            await saver.save_car(car, cid)
            st.saved += 1
            lg.info("saved %s depth=%s", cid, depth)
        except Exception as e:
            st.errors.append(f"save {lid}: {e}")
            lg.exception("offline save failed %s", lid)

    return st


def load_vdp_html_map(*paths: str | Path) -> Dict[str, str]:
    """Map listing_id → HTML from files named ``vdp_<id>_*.html`` or containing the id."""
    out: Dict[str, str] = {}
    for raw in paths:
        p = Path(raw)
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        stem = p.stem
        lid = None
        if stem.startswith("vdp_"):
            # vdp_789850281_min → 789850281
            parts = stem.split("_")
            if len(parts) >= 2 and parts[1].isdigit():
                lid = parts[1]
        if not lid:
            parsed = parse_vdp_page(text)
            if parsed.get("ok") and parsed.get("listing_id"):
                lid = str(parsed["listing_id"])
        if lid:
            out[lid] = text
    return out


async def run_autotrader_ingest(
    client: AsyncAutotraderClient,
    saver: CarSaver,
    config: dict,
    *,
    stats: Optional[AutotraderStats] = None,
    logger: Optional[logging.Logger] = None,
) -> AutotraderStats:
    """
    SRP pages → optional VDP enrich → Postgres save.

    Config keys (autotrader / root):
      max_pages, max_cars, fetch_vdp (bool), start_page,
      list_page_delay_min/max, detail_concurrency
    """
    lg = logger or log
    st = stats or AutotraderStats()
    at = config.get("autotrader") or {}
    http = config.get("http") or {}

    max_pages = int(at.get("max_pages") or config.get("max_pages") or 0) or 0
    max_cars = int(at.get("max_cars") or config.get("max_cars") or 0) or 0
    start_page = int(at.get("start_page") or 1)
    fetch_vdp = bool(at.get("fetch_vdp", True))
    delay_min = float(http.get("list_page_delay_min", at.get("list_page_delay_min", 0.5)))
    delay_max = float(http.get("list_page_delay_max", at.get("list_page_delay_max", 1.5)))
    detail_conc = int(http.get("concurrency") or at.get("detail_concurrency") or 3)

    seen: Set[str] = set()
    page = start_page
    pages_done = 0

    while True:
        if max_pages > 0 and pages_done >= max_pages:
            break
        if max_cars > 0 and st.saved >= max_cars:
            break

        try:
            html = await client.fetch_srp(page)
            parsed = parse_srp_page(html)
            if not parsed.get("ok"):
                raise RuntimeError("SRP parse failed")
            st.list_pages_ok += 1
        except Exception as e:
            st.list_pages_fail += 1
            st.errors.append(f"srp page={page}: {e}")
            lg.exception("Autotrader SRP page %s failed", page)
            break

        active_ids = list(parsed["active_ids"])
        inventory = parsed["inventory"]
        total = parsed.get("total_count")
        lg.info(
            "Autotrader SRP page=%s ids=%s total_count=%s inventory=%s",
            page,
            len(active_ids),
            total,
            len(inventory),
        )

        if not active_ids:
            lg.info("Autotrader: empty activeResults on page %s — stop", page)
            break

        # detail queue for this page
        sem = asyncio.Semaphore(max(1, detail_conc))

        async def handle_one(lid: str) -> None:
            nonlocal st
            if lid in seen:
                st.skipped += 1
                return
            if max_cars > 0 and st.saved >= max_cars:
                return
            seen.add(lid)
            st.listings_seen += 1
            card = inventory.get(lid)
            depth = "srp"
            listing = card
            if fetch_vdp:
                async with sem:
                    try:
                        vhtml = await client.fetch_vdp(lid)
                        vparsed = parse_vdp_page(vhtml, listing_id=lid)
                        if vparsed.get("ok") and vparsed.get("listing"):
                            listing = vparsed["listing"]
                            depth = "vdp"
                            st.details_ok += 1
                        else:
                            st.details_fail += 1
                            st.errors.append(f"vdp empty {lid}")
                    except Exception as e:
                        st.details_fail += 1
                        st.errors.append(f"vdp {lid}: {e}")
                        lg.warning("Autotrader VDP %s failed: %s", lid, e)

            if not isinstance(listing, dict):
                st.skipped += 1
                return
            try:
                car = normalize_listing(listing, listing_id=lid, depth=depth)
                cid = car_id_for_listing(lid)
                await saver.save_car(car, cid)
                st.saved += 1
            except Exception as e:
                st.errors.append(f"save {lid}: {e}")
                lg.exception("Autotrader save failed %s", lid)

        await asyncio.gather(*(handle_one(lid) for lid in active_ids))

        pages_done += 1
        page += 1
        await asyncio.sleep(random.uniform(delay_min, delay_max))

    return st
