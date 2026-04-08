"""HTTP: листинг sh_sku_list и HTML карточки."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import aiohttp

SKU_LIST_PATH = "/motor/pc/sh/sh_sku_list"
DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://www.dongchedi.com",
    "Referer": "https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x",
}


def sku_list_url() -> str:
    q = urlencode({"aid": "1839", "app_name": "auto_web_pc"})
    return f"https://www.dongchedi.com{SKU_LIST_PATH}?{q}"


def build_list_form(
    *,
    page: int,
    limit: int,
    brand_id: Optional[str] = None,
    sh_city_name: Optional[str] = None,
    age_range: Optional[str] = None,
) -> Dict[str, str]:
    form: Dict[str, str] = {
        "page": str(max(1, page)),
        "limit": str(max(1, min(100, limit))),
    }
    if brand_id is not None and str(brand_id).strip():
        form["brand"] = str(brand_id).strip()
    if sh_city_name is not None and str(sh_city_name).strip():
        form["sh_city_name"] = str(sh_city_name).strip()
    if age_range is not None and str(age_range).strip():
        form["age_range"] = str(age_range).strip()
    return form


async def post_sku_list(
    session: aiohttp.ClientSession,
    *,
    page: int,
    limit: int,
    brand_id: Optional[str] = None,
    sh_city_name: Optional[str] = None,
    age_range: Optional[str] = None,
    timeout_s: float = 45.0,
    proxy: Optional[str] = None,
) -> Tuple[int, Optional[Dict[str, Any]]]:
    url = sku_list_url()
    form = build_list_form(
        page=page,
        limit=limit,
        brand_id=brand_id,
        sh_city_name=sh_city_name,
        age_range=age_range,
    )
    timeout = aiohttp.ClientTimeout(total=timeout_s + 15)
    try:
        async with session.post(url, data=form, timeout=timeout, proxy=proxy) as resp:
            status = resp.status
            if status != 200:
                return status, None
            try:
                return status, await resp.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError, aiohttp.ClientPayloadError):
                return status, None
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return 0, None


async def fetch_usedcar_html(
    session: aiohttp.ClientSession,
    sku_id: str,
    *,
    timeout_s: float = 45.0,
    proxy: Optional[str] = None,
) -> Tuple[int, Optional[str]]:
    url = f"https://www.dongchedi.com/usedcar/{sku_id}"
    timeout = aiohttp.ClientTimeout(total=timeout_s + 15)
    # Listing endpoint uses JSON headers, but card endpoint is sensitive to browser-like HTML headers.
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Referer": "https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x",
    }
    try:
        async with session.get(url, timeout=timeout, headers=headers, proxy=proxy) as resp:
            status = resp.status
            if status != 200:
                return status, None
            return status, await resp.text(encoding="utf-8", errors="replace")
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return 0, None


async def fetch_params_car_html(
    session: aiohttp.ClientSession,
    car_spec_id: str,
    *,
    referer_sku_id: str,
    timeout_s: float = 45.0,
    proxy: Optional[str] = None,
) -> Tuple[int, Optional[str]]:
    """HTML страницы параметров комплектации (新车指导价, полная комплектация)."""
    sid = str(car_spec_id).strip()
    if not sid:
        return 0, None
    url = f"https://www.dongchedi.com/auto/params-carIds-{sid}"
    ref = f"https://www.dongchedi.com/usedcar/{str(referer_sku_id).strip()}"
    timeout = aiohttp.ClientTimeout(total=timeout_s + 15)
    headers = {"Referer": ref}
    try:
        async with session.get(url, timeout=timeout, headers=headers, proxy=proxy) as resp:
            status = resp.status
            if status != 200:
                return status, None
            return status, await resp.text(encoding="utf-8", errors="replace")
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return 0, None
