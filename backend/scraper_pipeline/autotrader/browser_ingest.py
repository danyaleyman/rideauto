"""Autotrader ingest entirely inside Playwright (Akamai-safe with residential proxy)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Optional, Set

from scraper_pipeline.autotrader.parser import (
    car_id_for_listing,
    normalize_listing,
    parse_srp_page,
    parse_vdp_page,
)
from scraper_pipeline.autotrader.runtime_stats import AutotraderStats
from scraper_pipeline.autotrader.session import (
    _autotrader_proxy_url_list,
    collect_autotrader_cookies,
    save_cached_session,
)
from scraper_pipeline.encar.savers import CarSaver
from scraper_pipeline.resilience.browser_profile import resolve_browser_profile
from scraper_pipeline.resilience.session_bundle import SessionBundle
from scraper_pipeline.resilience.session_provider import playwright_proxy_config

log = logging.getLogger(__name__)


def run_autotrader_browser_ingest(
    saver: CarSaver,
    config: dict,
    *,
    logger: Optional[logging.Logger] = None,
    stats: Optional[AutotraderStats] = None,
) -> AutotraderStats:
    """SRP + VDP via Chromium; must run outside asyncio (Playwright sync)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(
            "Нужен Playwright: pip install playwright && playwright install chromium"
        ) from e

    lg = logger or log
    st = stats or AutotraderStats()
    at = config.get("autotrader") or {}
    http = config.get("http") or {}
    profile = resolve_browser_profile(config)

    base = str(at.get("base_url") or "https://www.autotrader.com").rstrip("/")
    start_url = str(at.get("bootstrap_start_url") or f"{base}/cars-for-sale/all-cars").strip()
    max_pages = int(at.get("max_pages") or config.get("max_pages") or 0) or 0
    max_cars = int(at.get("max_cars") or config.get("max_cars") or 0) or 0
    start_page = int(at.get("start_page") or 1)
    fetch_vdp = bool(at.get("fetch_vdp", True))
    timeout_ms = int(at.get("playwright_timeout_ms", 90000) or 90000)
    wait_ms = int(at.get("playwright_post_load_wait_ms", 2500) or 2500)
    headless = at.get("playwright_headless", True) is not False
    delay_min = float(http.get("list_page_delay_min", at.get("list_page_delay_min", 0.4)))
    delay_max = float(http.get("list_page_delay_max", at.get("list_page_delay_max", 1.2)))

    proxy_candidates: list[Optional[str]] = list(_autotrader_proxy_url_list(config)) or [None]
    last_err: Optional[Exception] = None

    for proxy_url in proxy_candidates:
        pw_proxy = playwright_proxy_config(proxy_url)
        launch_kw: Dict[str, Any] = {"headless": headless}
        if pw_proxy:
            launch_kw["proxy"] = pw_proxy
        lg.info(
            "Autotrader browser ingest: start=%s proxy=%s max_cars=%s max_pages=%s",
            start_url,
            bool(proxy_url),
            max_cars,
            max_pages,
        )
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(**launch_kw)
                try:
                    context = browser.new_context(
                        user_agent=profile.user_agent,
                        locale="en-US",
                        viewport={"width": 1440, "height": 900},
                        extra_http_headers={
                            "Accept-Language": "en-US,en;q=0.9",
                            "sec-ch-ua": profile.sec_ch_ua,
                            "sec-ch-ua-mobile": "?0",
                            "sec-ch-ua-platform": '"Windows"',
                        },
                    )
                    page = context.new_page()

                    def _goto(url: str) -> str:
                        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                        try:
                            page.wait_for_function(
                                "() => !!document.getElementById('__NEXT_DATA__') "
                                "|| document.body.innerText.toLowerCase().includes('unavailable')",
                                timeout=min(timeout_ms, 45000),
                            )
                        except Exception:
                            pass
                        if wait_ms > 0:
                            page.wait_for_timeout(wait_ms)
                        return page.content() or ""

                    # Warm / verify
                    html0 = _goto(start_url)
                    if "__NEXT_DATA__" not in html0:
                        raise RuntimeError("browser ingest: no __NEXT_DATA__ on start URL (Akamai?)")

                    cookies = collect_autotrader_cookies(context.cookies())
                    save_cached_session(
                        config,
                        SessionBundle(
                            source="autotrader",
                            cookies=cookies,
                            proxy_url=proxy_url,
                            user_agent=profile.user_agent,
                            impersonate_id=profile.impersonate,
                            obtained_at=time.time(),
                            meta={"fetch_mode": "playwright"},
                        ),
                        lg,
                    )

                    seen: Set[str] = set()
                    page_no = start_page
                    pages_done = 0
                    warm_html = html0

                    while True:
                        if max_pages > 0 and pages_done >= max_pages:
                            break
                        if max_cars > 0 and st.saved >= max_cars:
                            break

                        srp = (
                            start_url
                            if page_no <= 1
                            else f"{base}/cars-for-sale/all-cars?page={page_no}"
                        )
                        try:
                            if pages_done == 0 and page_no == start_page and warm_html:
                                html = warm_html
                                warm_html = ""
                            else:
                                html = _goto(srp)
                            parsed = parse_srp_page(html)
                            if not parsed.get("ok"):
                                raise RuntimeError("SRP parse failed")
                            st.list_pages_ok += 1
                        except Exception as e:
                            st.list_pages_fail += 1
                            st.errors.append(f"srp page={page_no}: {e}")
                            lg.exception("browser SRP page %s failed", page_no)
                            break

                        active_ids = list(parsed["active_ids"])
                        inventory = parsed["inventory"]
                        lg.info(
                            "browser SRP page=%s ids=%s inventory=%s",
                            page_no,
                            len(active_ids),
                            len(inventory),
                        )
                        if not active_ids:
                            break

                        for lid in active_ids:
                            if max_cars > 0 and st.saved >= max_cars:
                                break
                            if lid in seen:
                                st.skipped += 1
                                continue
                            seen.add(lid)
                            st.listings_seen += 1
                            listing = inventory.get(lid)
                            depth = "srp"
                            if fetch_vdp:
                                try:
                                    vhtml = _goto(f"{base}/cars-for-sale/vehicle/{lid}")
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
                                    lg.warning("browser VDP %s failed: %s", lid, e)

                            if not isinstance(listing, dict):
                                st.skipped += 1
                                continue
                            try:
                                car = normalize_listing(listing, listing_id=lid, depth=depth)
                                cid = car_id_for_listing(lid)
                                save_sync = getattr(saver, "_save_sync", None)
                                if callable(save_sync):
                                    save_sync(car, cid)
                                else:
                                    import asyncio

                                    asyncio.run(saver.save_car(car, cid))
                                st.saved += 1
                                lg.info(
                                    "saved %s depth=%s images=%s features=%s",
                                    cid,
                                    depth,
                                    len(car.get("images") or []),
                                    len(car.get("features") or []),
                                )
                            except Exception as e:
                                st.errors.append(f"save {lid}: {e}")
                                lg.exception("browser save failed %s", lid)

                            time.sleep(random.uniform(delay_min, delay_max))

                        pages_done += 1
                        page_no += 1
                        time.sleep(random.uniform(delay_min, delay_max))

                    return st
                finally:
                    browser.close()
        except Exception as e:
            last_err = e
            lg.warning("browser ingest failed proxy=%s: %s", bool(proxy_url), e)
            continue

    raise RuntimeError(f"Autotrader browser ingest failed all proxies. Last error: {last_err}")
