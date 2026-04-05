"""Async HTTP fetch for Che168 pages."""

from __future__ import annotations

import asyncio
from typing import Optional, Tuple

import aiohttp

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


async def fetch_text(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout_s: float = 45.0,
) -> Tuple[int, Optional[str]]:
    """Return (status, body text utf-8) or (0, None) on transport error."""
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout_s),
            headers=DEFAULT_HEADERS,
        ) as resp:
            text = await resp.text(errors="replace")
            return resp.status, text
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return 0, None
