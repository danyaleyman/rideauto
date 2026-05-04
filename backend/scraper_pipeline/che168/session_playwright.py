"""
Получение кук Che168 Global через Chromium (Playwright) на том же исходящем IP, что и API.

Важно: если bootstrap шёл через прокси, в config выставляется che168._session_proxy_url —
AsyncChe168Client должен использовать только этот URL, иначе сессия сбросится (другой IP).
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

CHE168_COOKIE_MARKERS = ("che168", "autohome", "autoimg")


def playwright_proxy_config(proxy_url: Optional[str]) -> Optional[Dict[str, str]]:
    """URL вида http(s)://user:pass@host:port → dict для Chromium.launch(proxy=...)."""
    if not proxy_url or not str(proxy_url).strip():
        return None
    p = urllib.parse.urlsplit(str(proxy_url).strip())
    if not p.hostname:
        return None
    scheme = (p.scheme or "http").lower()
    port = p.port
    if port is None:
        port = 443 if scheme == "https" else 80
    server = f"{scheme}://{p.hostname}:{port}"
    cfg: Dict[str, str] = {"server": server}
    if p.username:
        cfg["username"] = urllib.parse.unquote(p.username)
    if p.password:
        cfg["password"] = urllib.parse.unquote(p.password)
    return cfg


def _pick_bootstrap_proxy_url(config: dict) -> Optional[str]:
    """Тот же URL, что потом у aiohttp при proxy.sticky_session (обычно urls[0])."""
    ch = config.get("che168", {}) or {}
    manual = str(ch.get("bootstrap_proxy_url") or "").strip()
    if manual:
        return manual
    px = config.get("proxy", {}) or {}
    if px.get("enabled"):
        urls = px.get("urls") or []
        if urls:
            return str(urls[0]).strip()
    return None


def _relevant_browser_cookies(ck_list: list) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for c in ck_list:
        if not isinstance(c, dict):
            continue
        dom = str(c.get("domain") or "").lower()
        if not any(m in dom for m in CHE168_COOKIE_MARKERS):
            continue
        name = c.get("name")
        val = c.get("value")
        if name and val is not None and str(val).strip():
            out[str(name)] = str(val)
    return out


def _url_append_query(url: str, extra: Dict[str, str]) -> str:
    p = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(p.query, keep_blank_values=True))
    for k, v in extra.items():
        if v and k not in q:
            q[k] = v
    new_q = urllib.parse.urlencode(q)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, new_q, p.fragment))


def bootstrap_che168_browser_cookies_sync(
    config: dict,
    log: logging.Logger,
) -> Tuple[Dict[str, str], Optional[str]]:
    """
    Открывает global.che168.com в Chromium, возвращает (cookies_name_value, proxy_url_used).

    Требует: pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(
            "Нужен Playwright: pip install playwright && playwright install chromium"
        ) from e

    ch = config.get("che168", {}) or {}
    start_url = str(ch.get("bootstrap_start_url", "https://global.che168.com/")).strip()
    dev = str(ch.get("deviceid", "")).strip()
    ap = str(ch.get("app_id", "global.m"))
    lang = str(ch.get("language", "en"))
    api_base = str(ch.get("base_url", "https://globalapi.che168.com/api/v1")).rstrip("/")
    origin = str(ch.get("origin", "https://global.che168.com")).rstrip("/")
    referer = str(ch.get("referer", f"{origin}/"))
    if dev:
        start_url = _url_append_query(start_url, {"deviceid": dev, "_appid": ap, "language": lang})
    timeout_ms = int(ch.get("playwright_timeout_ms", 60000) or 60000)
    wait_ms = int(ch.get("playwright_post_load_wait_ms", 2500) or 2500)
    headless = ch.get("playwright_headless", True) is not False

    proxy_url = _pick_bootstrap_proxy_url(config)
    pw_proxy = playwright_proxy_config(proxy_url)
    if proxy_url:
        log.info("Che168 bootstrap: Chromium через прокси (тот же IP, что и для API)")
    else:
        log.info("Che168 bootstrap: Chromium без прокси (тот же хост, что и скрейпер)")

    uas = config.get("user_agents") or []
    ua = str(uas[0]) if uas else (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    collected: Dict[str, str] = {}
    with sync_playwright() as p:
        launch_kw: Dict[str, Any] = {"headless": headless}
        if pw_proxy:
            launch_kw["proxy"] = pw_proxy
        browser = p.chromium.launch(**launch_kw)
        try:
            context = browser.new_context(
                user_agent=ua,
                locale="en-US",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            page.goto(start_url, wait_until="domcontentloaded", timeout=timeout_ms)
            time.sleep(min(30.0, max(0.5, wait_ms / 1000.0)))
            try:
                page.wait_for_load_state("networkidle", timeout=min(15000, timeout_ms))
            except Exception:
                log.debug("Che168 bootstrap: networkidle timeout (игнор)")
            if dev and ch.get("playwright_api_warmup", True) is not False:
                warm_brand = str(ch.get("bootstrap_warmup_brandid", "276") or "276")
                try:
                    wr = context.request.get(
                        f"{api_base}/search",
                        params={
                            "_appid": ap,
                            "deviceid": dev,
                            "language": lang,
                            "brandid": warm_brand,
                            "pageindex": "1",
                            "pagesize": "10",
                            "sort": "0",
                            "vehicle_list": "0",
                        },
                        headers={
                            "Accept": "application/json, text/plain, */*",
                            "Origin": origin,
                            "Referer": referer,
                        },
                        timeout=timeout_ms,
                    )
                    log.info("Che168 bootstrap: warmup GET /search status=%s", wr.status)
                    if wr.ok:
                        try:
                            body = wr.json()
                            layer = body.get("result") if isinstance(body, dict) else None
                            if isinstance(layer, dict):
                                log.info(
                                    "Che168 bootstrap: warmup totalcount=%s carlist=%s",
                                    layer.get("totalcount"),
                                    len(layer.get("carlist") or []) if isinstance(layer.get("carlist"), list) else None,
                                )
                        except Exception:
                            pass
                except Exception as e:
                    log.warning("Che168 bootstrap: warmup /search failed: %s", e)
                time.sleep(0.3)
            collected = _relevant_browser_cookies(context.cookies())
        finally:
            browser.close()

    if not collected.get("sessionid"):
        log.warning(
            "Che168 bootstrap: sessionid не найден в куках (получено ключей=%s). "
            "Проверьте доступность сайта / прокси.",
            list(collected.keys())[:20],
        )
    else:
        log.info("Che168 bootstrap: sessionid получен, всего релевантных кук=%s", len(collected))
    return collected, proxy_url


def apply_playwright_bootstrap_to_config(config: dict, log: logging.Logger) -> None:
    """Мутирует config: cookies + опционально _session_proxy_url для AsyncChe168Client."""
    boot, proxy_used = bootstrap_che168_browser_cookies_sync(config, log)
    ch = config.setdefault("che168", {})
    base_cookies = dict(ch.get("cookies") or {}) if isinstance(ch.get("cookies"), dict) else {}
    merged = {**base_cookies, **boot}
    for k in ("is_overseas", "area"):
        if k in base_cookies and k not in merged:
            merged[k] = base_cookies[k]
    if "is_overseas" not in merged:
        merged["is_overseas"] = str(ch.get("is_overseas", "1"))
    if "area" not in merged:
        merged["area"] = str(ch.get("area", "0"))
    ch["cookies"] = merged
    if boot.get("sessionid"):
        ch["sessionid"] = boot["sessionid"]
    if proxy_used:
        ch["_session_proxy_url"] = proxy_used
        log.info("Che168: зафиксирован _session_proxy_url для совпадения IP с браузером")
    else:
        ch.pop("_session_proxy_url", None)
