"""Async HTTP client for Autotrader SRP/VDP HTML (curl_cffi + auto session)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Awaitable
from urllib.parse import urlencode

from scraper_pipeline.autotrader.session import ensure_autotrader_session
from scraper_pipeline.resilience.browser_profile import resolve_browser_profile
from scraper_pipeline.resilience.transport import AsyncHttpTransport

log = logging.getLogger(__name__)

# Re-export compatible helper used by older call sites / docs
def load_cookie_header(config: dict) -> str:
    """Prefer AUTOTRADER_COOKIE env, then config cookie, then cookie_file."""
    env = (os.environ.get("AUTOTRADER_COOKIE") or "").strip()
    if env:
        return env
    at = config.get("autotrader") or {}
    cfg_cookie = str(at.get("cookie") or "").strip()
    if cfg_cookie:
        return cfg_cookie
    file_path = (
        os.environ.get("AUTOTRADER_COOKIE_FILE")
        or at.get("cookie_file")
        or ""
    ).strip()
    if file_path:
        p = Path(file_path)
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    return ""


def is_autotrader_challenge_html(html: str, *, status: int = 200) -> bool:
    if status in (403, 429, 503):
        return True
    if not html:
        return True
    low = html.lower()
    if "__next_data__" in low:
        return False
    markers = (
        "akamai-block",
        "access denied",
        "page unavailable",
        "incident number",
        "robot or spider",
        "captcha",
        "/_sec/cp_challenge",
    )
    return any(m in low for m in markers)


class AsyncAutotraderClient:
    def __init__(
        self,
        config: dict,
        logger: Optional[logging.Logger] = None,
        *,
        auto_bootstrap: bool = True,
    ):
        self.config = config
        self.log = logger or log
        at = config.get("autotrader") or {}
        self.base = str(at.get("base_url") or "https://www.autotrader.com").rstrip("/")
        http = config.get("http") or {}
        self._auto_bootstrap = auto_bootstrap and at.get("auto_bootstrap", True) is not False
        self._max_challenge_retries = int(at.get("challenge_retries", 2) or 2)
        self._profile = resolve_browser_profile(config)
        self._transport = AsyncHttpTransport(config, source="autotrader", logger=self.log)
        self._cookie = load_cookie_header(config)
        self._ua = str(at.get("user_agent") or http.get("user_agent") or self._profile.user_agent)
        self._cookies_map: Dict[str, str] = dict(at.get("_session_cookies") or {})
        self._proxy = str(at.get("_session_proxy_url") or at.get("proxy_url") or "").strip() or None
        self._opened = False
        self._on_refresh: Optional[Callable[[], Awaitable[None]]] = None

    async def __aenter__(self) -> "AsyncAutotraderClient":
        await self.open()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def set_refresh_hook(self, hook: Callable[[], Awaitable[None]]) -> None:
        self._on_refresh = hook

    def _apply_session_from_config(self) -> None:
        at = self.config.get("autotrader") or {}
        self._cookie = load_cookie_header(self.config)
        self._cookies_map = dict(at.get("_session_cookies") or {})
        self._ua = str(at.get("user_agent") or self._ua or self._profile.user_agent)
        self._proxy = str(at.get("_session_proxy_url") or at.get("proxy_url") or "").strip() or None

    async def open(self) -> None:
        if self._opened:
            return
        if self._auto_bootstrap and not self._cookie and not self._cookies_map:
            import asyncio

            await asyncio.to_thread(ensure_autotrader_session, self.config, self.log)
            self._apply_session_from_config()
        await self._transport.__aenter__()
        self._opened = True
        if self._cookie or self._cookies_map:
            self.log.info(
                "Autotrader client open: cookie_header=%s cookie_map=%s proxy=%s impersonate=%s",
                len(self._cookie),
                len(self._cookies_map),
                bool(self._proxy),
                self._profile.impersonate,
            )
        else:
            self.log.warning(
                "Autotrader: no session cookies — live requests likely blocked; "
                "set AUTOTRADER_PROXY_URL (residential) once in .env"
            )

    async def close(self) -> None:
        if self._opened:
            await self._transport.__aexit__(None, None, None)
        self._opened = False

    async def refresh_session(self) -> None:
        import asyncio

        self.log.info("Autotrader: refreshing browser session after challenge")
        # Playwright sync API cannot run inside the running event loop.
        await asyncio.to_thread(
            ensure_autotrader_session, self.config, self.log, force_refresh=True
        )
        self._apply_session_from_config()
        if self._on_refresh:
            await self._on_refresh()

    def srp_url(self, page: int = 1, *, extra_query: Optional[Dict[str, Any]] = None) -> str:
        q: Dict[str, Any] = {}
        if extra_query:
            q.update(extra_query)
        if page and int(page) > 1:
            q["page"] = int(page)
        path = "/cars-for-sale/all-cars"
        if q:
            return f"{self.base}{path}?{urlencode(q)}"
        return f"{self.base}{path}"

    def vdp_url(self, listing_id: str) -> str:
        return f"{self.base}/cars-for-sale/vehicle/{listing_id}"

    def _request_headers(self) -> Dict[str, str]:
        h = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{self.base}/cars-for-sale/all-cars",
            "User-Agent": self._ua,
        }
        if self._cookie:
            h["Cookie"] = self._cookie
        return h

    async def fetch_html(self, url: str) -> str:
        if not self._opened:
            await self.open()

        last_err: Optional[Exception] = None
        for attempt in range(self._max_challenge_retries + 1):
            resp = await self._transport.request(
                "GET",
                url,
                headers=self._request_headers(),
                cookies=self._cookies_map or None,
                proxy=self._proxy,
                expect_json=False,
            )
            text = resp.text or ""
            if resp.error and not text:
                last_err = RuntimeError(f"transport error for {url}: {resp.error}")
                continue
            if is_autotrader_challenge_html(text, status=resp.status):
                last_err = RuntimeError(
                    f"Autotrader challenge/block HTTP {resp.status} for {url} (body_len={len(text)})"
                )
                self.log.warning("%s (attempt %s)", last_err, attempt + 1)
                if attempt < self._max_challenge_retries and self._auto_bootstrap:
                    await self.refresh_session()
                    continue
                raise last_err
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status} for {url} (body_len={len(text)})")
            if "__NEXT_DATA__" not in text:
                raise RuntimeError(f"No __NEXT_DATA__ in response for {url} (status={resp.status})")
            return text

        raise last_err or RuntimeError(f"fetch failed for {url}")

    async def fetch_srp(self, page: int = 1) -> str:
        return await self.fetch_html(self.srp_url(page))

    async def fetch_vdp(self, listing_id: str) -> str:
        return await self.fetch_html(self.vdp_url(str(listing_id)))
