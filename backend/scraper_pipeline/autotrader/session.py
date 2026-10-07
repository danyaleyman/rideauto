"""Autotrader session bootstrap: Playwright → Akamai/AT cookies for HTTP (curl_cffi)."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from scraper_pipeline.resilience.browser_profile import resolve_browser_profile
from scraper_pipeline.resilience.session_bundle import SessionBundle
from scraper_pipeline.resilience.session_provider import (
    PlaywrightSessionProvider,
    playwright_proxy_config,
)

log = logging.getLogger(__name__)

AUTOTRADER_COOKIE_DOMAIN_MARKERS: Tuple[str, ...] = (
    "autotrader",
    "akamai",
    "akam",
)
AUTOTRADER_COOKIE_NAME_PREFIXES: Tuple[str, ...] = (
    "_abck",
    "bm_",
    "ak_",
    "akamai",
    "AT-",
    "at_",
    "JSESSION",
)


def _pick_autotrader_bootstrap_proxy_url(config: dict) -> Optional[str]:
    at = config.get("autotrader") or {}
    for key in ("bootstrap_proxy_url", "proxy_url"):
        manual = str(at.get(key) or "").strip()
        if manual:
            return manual
    env = (os.environ.get("AUTOTRADER_PROXY_URL") or os.environ.get("AUTOTRADER_BOOTSTRAP_PROXY_URL") or "").strip()
    if env:
        return env
    px = config.get("proxy") or {}
    if px.get("enabled"):
        urls = px.get("urls") or []
        if urls:
            return str(urls[0]).strip()
    return None


def collect_autotrader_cookies(ck_list: list) -> Dict[str, str]:
    """Keep Akamai + Autotrader cookies by domain and well-known name prefixes."""
    out: Dict[str, str] = {}
    for c in ck_list:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "").strip()
        val = c.get("value")
        if not name or val is None or not str(val).strip():
            continue
        dom = str(c.get("domain") or "").lower()
        name_l = name.lower()
        keep = any(m in dom for m in AUTOTRADER_COOKIE_DOMAIN_MARKERS)
        if not keep:
            keep = any(name_l.startswith(p.lower()) for p in AUTOTRADER_COOKIE_NAME_PREFIXES)
        if keep:
            out[name] = str(val)
    return out


def cookie_header_from_map(cookies: Dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items() if k and v is not None)


def session_cache_path(config: dict) -> Optional[Path]:
    at = config.get("autotrader") or {}
    raw = (
        os.environ.get("AUTOTRADER_SESSION_FILE")
        or at.get("session_file")
        or ""
    ).strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def load_cached_session(config: dict, log_: logging.Logger) -> Optional[SessionBundle]:
    path = session_cache_path(config)
    if not path or not path.is_file():
        return None
    at = config.get("autotrader") or {}
    max_age = float(at.get("session_max_age_sec") or 6 * 3600)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log_.warning("Autotrader session cache unreadable %s: %s", path, e)
        return None
    if not isinstance(data, dict):
        return None
    bundle = SessionBundle.from_mapping("autotrader", data)
    if bundle.age_seconds > max_age:
        log_.info("Autotrader session cache stale age=%.0fs > %.0fs", bundle.age_seconds, max_age)
        return None
    if not bundle.cookies:
        return None
    log_.info(
        "Autotrader session cache hit age=%.0fs cookies=%s path=%s",
        bundle.age_seconds,
        len(bundle.cookies),
        path,
    )
    return bundle


def save_cached_session(config: dict, bundle: SessionBundle, log_: logging.Logger) -> None:
    path = session_cache_path(config)
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cookies": bundle.cookies,
            "proxy_url": bundle.proxy_url,
            "user_agent": bundle.user_agent,
            "impersonate_id": bundle.impersonate_id,
            "obtained_at": bundle.obtained_at,
            "meta": bundle.meta,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        log_.info("Autotrader session cache saved %s cookies=%s", path, len(bundle.cookies))
    except OSError as e:
        log_.warning("Autotrader session cache write failed: %s", e)


class AutotraderSessionProvider(PlaywrightSessionProvider):
    """Open Autotrader in Chromium, wait past Akamai, export cookies for HTTP client."""

    source = "autotrader"
    cookie_markers = AUTOTRADER_COOKIE_DOMAIN_MARKERS

    def _bootstrap(self, config: dict, log_: logging.Logger) -> SessionBundle:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ImportError(
                "Нужен Playwright: pip install playwright && playwright install chromium"
            ) from e

        profile = resolve_browser_profile(config)
        at = config.get("autotrader") or {}
        start_url = str(
            at.get("bootstrap_start_url")
            or "https://www.autotrader.com/cars-for-sale/all-cars"
        ).strip()
        timeout_ms = int(at.get("playwright_timeout_ms", 90000) or 90000)
        wait_ms = int(at.get("playwright_post_load_wait_ms", 4000) or 4000)
        headless = at.get("playwright_headless", True) is not False
        proxy_url = _pick_autotrader_bootstrap_proxy_url(config)
        pw_proxy = playwright_proxy_config(proxy_url)
        ua = profile.user_agent

        launch_kw: Dict[str, Any] = {"headless": headless}
        if pw_proxy:
            launch_kw["proxy"] = pw_proxy

        log_.info(
            "Autotrader SessionProvider: bootstrap url=%s headless=%s proxy=%s",
            start_url,
            headless,
            bool(proxy_url),
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kw)
            try:
                context = browser.new_context(
                    user_agent=ua,
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
                page.goto(start_url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Wait for Next.js payload or challenge to settle
                try:
                    page.wait_for_function(
                        "() => !!document.getElementById('__NEXT_DATA__') "
                        "|| document.body.innerText.toLowerCase().includes('unavailable')",
                        timeout=timeout_ms,
                    )
                except Exception:
                    pass
                if wait_ms > 0:
                    page.wait_for_timeout(wait_ms)
                html = page.content() or ""
                has_next = "__NEXT_DATA__" in html
                blocked = (
                    "akamai-block" in html.lower()
                    or "page unavailable" in html.lower()
                    or ("incident number" in html.lower() and not has_next)
                )
                collected = collect_autotrader_cookies(context.cookies())
                if blocked and not has_next:
                    log_.warning(
                        "Autotrader SessionProvider: still blocked after bootstrap "
                        "(cookies=%s). Set autotrader.bootstrap_proxy_url / AUTOTRADER_PROXY_URL "
                        "to a residential proxy.",
                        len(collected),
                    )
                elif has_next:
                    log_.info(
                        "Autotrader SessionProvider: __NEXT_DATA__ ok, cookies=%s",
                        len(collected),
                    )
                else:
                    log_.warning(
                        "Autotrader SessionProvider: no __NEXT_DATA__ (cookies=%s)",
                        len(collected),
                    )
            finally:
                browser.close()

        return SessionBundle(
            source="autotrader",
            cookies=collected,
            proxy_url=proxy_url,
            user_agent=ua,
            impersonate_id=profile.impersonate,
            obtained_at=time.time(),
            meta={"headless": headless, "has_next_data": has_next, "blocked": blocked},
        )


def apply_session_bundle_to_autotrader_config(
    config: dict, bundle: SessionBundle, log_: logging.Logger
) -> None:
    at = config.setdefault("autotrader", {})
    at["cookie"] = cookie_header_from_map(bundle.cookies)
    at["_session_cookies"] = dict(bundle.cookies)
    if bundle.user_agent:
        at["user_agent"] = bundle.user_agent
    if bundle.proxy_url:
        at["_session_proxy_url"] = bundle.proxy_url
        log_.info("Autotrader: sticky _session_proxy_url for HTTP egress")
    else:
        at.pop("_session_proxy_url", None)
    at["_session_bundle_meta"] = bundle.to_public_dict()


def ensure_autotrader_session(
    config: dict,
    log_: logging.Logger,
    *,
    force_refresh: bool = False,
) -> SessionBundle:
    """
    Load cached session or Playwright-bootstrap a new one.
    Writes cookie header into config.autotrader for the HTTP client.
    """
    at = config.setdefault("autotrader", {})
    # Explicit env cookie still wins (ops override), unless force_refresh.
    env_cookie = (os.environ.get("AUTOTRADER_COOKIE") or "").strip()
    if env_cookie and not force_refresh:
        at["cookie"] = env_cookie
        log_.info("Autotrader: using AUTOTRADER_COOKIE env (%d chars)", len(env_cookie))
        return SessionBundle(
            source="autotrader",
            cookies={},
            user_agent=str(at.get("user_agent") or "") or None,
            meta={"from_env_cookie": True},
        )

    if not force_refresh:
        cached = load_cached_session(config, log_)
        if cached:
            apply_session_bundle_to_autotrader_config(config, cached, log_)
            return cached

    skip_pw = str(at.get("skip_playwright_bootstrap") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if skip_pw:
        log_.warning("Autotrader: skip_playwright_bootstrap=1 — live fetch may 403")
        return SessionBundle(source="autotrader", cookies={}, meta={"skipped": True})

    provider = AutotraderSessionProvider()
    bundle = provider.acquire(config, log_)
    apply_session_bundle_to_autotrader_config(config, bundle, log_)
    save_cached_session(config, bundle, log_)
    return bundle
