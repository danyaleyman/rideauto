"""Async HTTP client for Autotrader SRP/VDP HTML pages."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import aiohttp

log = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/142.0.0.0 Safari/537.36"
)


def load_cookie_header(config: dict) -> str:
    """Prefer AUTOTRADER_COOKIE env, then cookie_file, then config cookie string."""
    env = (os.environ.get("AUTOTRADER_COOKIE") or "").strip()
    if env:
        return env
    at = config.get("autotrader") or {}
    file_path = (
        os.environ.get("AUTOTRADER_COOKIE_FILE")
        or at.get("cookie_file")
        or ""
    ).strip()
    if file_path:
        p = Path(file_path)
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    return str(at.get("cookie") or "").strip()


class AsyncAutotraderClient:
    def __init__(self, config: dict, logger: Optional[logging.Logger] = None):
        self.config = config
        self.log = logger or log
        at = config.get("autotrader") or {}
        self.base = str(at.get("base_url") or "https://www.autotrader.com").rstrip("/")
        http = config.get("http") or {}
        self.timeout = aiohttp.ClientTimeout(
            total=float(http.get("timeout_total", 45) or 45),
            connect=float(http.get("timeout_connect", 15) or 15),
            sock_read=float(http.get("timeout_sock_read", 35) or 35),
        )
        self._cookie = load_cookie_header(config)
        self._ua = str(at.get("user_agent") or http.get("user_agent") or DEFAULT_UA)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "AsyncAutotraderClient":
        await self.open()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def open(self) -> None:
        if self._session and not self._session.closed:
            return
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{self.base}/cars-for-sale/all-cars",
        }
        if self._cookie:
            headers["Cookie"] = self._cookie
            self.log.info("Autotrader: cookie header loaded (%d chars)", len(self._cookie))
        else:
            self.log.warning(
                "Autotrader: no cookie — live requests may get Akamai 403; "
                "set AUTOTRADER_COOKIE or autotrader.cookie_file"
            )
        self._session = aiohttp.ClientSession(headers=headers, timeout=self.timeout)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

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

    async def fetch_html(self, url: str) -> str:
        if not self._session:
            await self.open()
        assert self._session is not None
        async with self._session.get(url) as resp:
            text = await resp.text(errors="replace")
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status} for {url} (body_len={len(text)})")
            if "incapsula" in text.lower() and "__NEXT_DATA__" not in text:
                raise RuntimeError(f"Likely bot challenge for {url}")
            if "__NEXT_DATA__" not in text:
                raise RuntimeError(f"No __NEXT_DATA__ in response for {url} (status={resp.status})")
            return text

    async def fetch_srp(self, page: int = 1) -> str:
        return await self.fetch_html(self.srp_url(page))

    async def fetch_vdp(self, listing_id: str) -> str:
        return await self.fetch_html(self.vdp_url(str(listing_id)))
