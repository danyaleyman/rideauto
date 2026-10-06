"""SessionProvider: Playwright bootstrap → SessionBundle (browser = session factory)."""

from __future__ import annotations

import logging
import time
import urllib.parse
from typing import Any, Dict, Optional, Protocol, Tuple

from scraper_pipeline.resilience.browser_profile import resolve_browser_profile
from scraper_pipeline.resilience.session_bundle import SessionBundle

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


def _pick_che168_bootstrap_proxy_url(config: dict) -> Optional[str]:
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


def _relevant_browser_cookies(ck_list: list, markers: Tuple[str, ...]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for c in ck_list:
        if not isinstance(c, dict):
            continue
        dom = str(c.get("domain") or "").lower()
        if not any(m in dom for m in markers):
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


class SessionProvider(Protocol):
    def acquire(self, config: dict, log: logging.Logger) -> SessionBundle: ...

    def refresh(self, config: dict, log: logging.Logger) -> SessionBundle: ...


class PlaywrightSessionProvider:
    """Общий Playwright session provider (CDP Chromium). Источник задаётся подклассом/параметрами."""

    source: str = "generic"
    cookie_markers: Tuple[str, ...] = ()

    def acquire(self, config: dict, log: logging.Logger) -> SessionBundle:
        return self._bootstrap(config, log)

    def refresh(self, config: dict, log: logging.Logger) -> SessionBundle:
        return self._bootstrap(config, log)

    def _bootstrap(self, config: dict, log: logging.Logger) -> SessionBundle:
        raise NotImplementedError


class Che168SessionProvider(PlaywrightSessionProvider):
    source = "che168"
    cookie_markers = CHE168_COOKIE_MARKERS

    def _bootstrap(self, config: dict, log: logging.Logger) -> SessionBundle:
        from scraper_pipeline.che168.client import ensure_che168_deviceid

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ImportError(
                "Нужен Playwright: pip install playwright && playwright install chromium"
            ) from e

        ensure_che168_deviceid(config, log)
        profile = resolve_browser_profile(config)
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

        proxy_url = _pick_che168_bootstrap_proxy_url(config)
        pw_proxy = playwright_proxy_config(proxy_url)
        if proxy_url:
            log.info("Che168 SessionProvider: Chromium через sticky proxy")
        else:
            log.info("Che168 SessionProvider: Chromium без прокси")

        ua = profile.user_agent
        # Anti-automation baseline (no second browser stack).
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ]

        collected: Dict[str, str] = {}
        with sync_playwright() as p:
            launch_kw: Dict[str, Any] = {"headless": headless, "args": launch_args}
            if pw_proxy:
                launch_kw["proxy"] = pw_proxy
            browser = p.chromium.launch(**launch_kw)
            try:
                context = browser.new_context(
                    user_agent=ua,
                    locale="en-US",
                    viewport={"width": 1280, "height": 720},
                    extra_http_headers={
                        "Accept-Language": profile.accept_language,
                        "sec-ch-ua": profile.sec_ch_ua,
                        "sec-ch-ua-mobile": profile.sec_ch_ua_mobile,
                        "sec-ch-ua-platform": profile.sec_ch_ua_platform,
                    },
                )
                page = context.new_page()
                page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                page.goto(start_url, wait_until="domcontentloaded", timeout=timeout_ms)
                time.sleep(min(30.0, max(0.5, wait_ms / 1000.0)))
                try:
                    page.wait_for_load_state("networkidle", timeout=min(15000, timeout_ms))
                except Exception:
                    log.debug("Che168 SessionProvider: networkidle timeout (игнор)")
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
                                "User-Agent": ua,
                            },
                            timeout=timeout_ms,
                        )
                        log.info("Che168 SessionProvider: warmup GET /search status=%s", wr.status)
                    except Exception as e:
                        log.warning("Che168 SessionProvider: warmup /search failed: %s", e)
                    time.sleep(0.3)
                collected = _relevant_browser_cookies(context.cookies(), self.cookie_markers)
            finally:
                browser.close()

        if not collected.get("sessionid"):
            log.warning(
                "Che168 SessionProvider: sessionid не найден (keys=%s)",
                list(collected.keys())[:20],
            )
        else:
            log.info("Che168 SessionProvider: sessionid ok, cookies=%s", len(collected))

        return SessionBundle(
            source="che168",
            cookies=collected,
            proxy_url=proxy_url,
            user_agent=ua,
            impersonate_id=profile.impersonate,
            device_id=dev or None,
            obtained_at=time.time(),
            meta={"headless": headless},
        )


def apply_session_bundle_to_che168_config(config: dict, bundle: SessionBundle, log: logging.Logger) -> None:
    """Мутирует config: cookies + sticky proxy из SessionBundle."""
    ch = config.setdefault("che168", {})
    base_cookies = dict(ch.get("cookies") or {}) if isinstance(ch.get("cookies"), dict) else {}
    merged = {**base_cookies, **(bundle.cookies or {})}
    for k in ("is_overseas", "area"):
        if k in base_cookies and k not in merged:
            merged[k] = base_cookies[k]
    if "is_overseas" not in merged:
        merged["is_overseas"] = str(ch.get("is_overseas", "1"))
    if "area" not in merged:
        merged["area"] = str(ch.get("area", "0"))
    ch["cookies"] = merged
    if bundle.sessionid():
        ch["sessionid"] = bundle.sessionid()
    if bundle.proxy_url:
        ch["_session_proxy_url"] = bundle.proxy_url
        log.info("Che168: зафиксирован _session_proxy_url для совпадения IP с браузером")
    else:
        ch.pop("_session_proxy_url", None)
    if bundle.device_id:
        ch["deviceid"] = bundle.device_id
    ch["_session_bundle_meta"] = bundle.to_public_dict()


def apply_playwright_bootstrap_to_config(config: dict, log: logging.Logger) -> SessionBundle:
    """Совместимый entrypoint: acquire Che168 session и записать в config."""
    provider = Che168SessionProvider()
    bundle = provider.acquire(config, log)
    apply_session_bundle_to_che168_config(config, bundle, log)
    return bundle
