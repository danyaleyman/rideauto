"""Optional browser fallback for Dongchedi card HTML."""

from __future__ import annotations

from typing import Optional, Tuple


_PLAYWRIGHT_UNAVAILABLE = False


async def fetch_usedcar_html_playwright(
    sku_id: str,
    *,
    timeout_s: float = 25.0,
) -> Tuple[int, Optional[str]]:
    """
    Fetch usedcar page via headless browser for anti-bot protected hosts.
    Returns (status, html) similar to HTTP client helpers.
    """
    global _PLAYWRIGHT_UNAVAILABLE
    if _PLAYWRIGHT_UNAVAILABLE:
        return 0, None

    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception:
        _PLAYWRIGHT_UNAVAILABLE = True
        return 0, None

    url = f"https://www.dongchedi.com/usedcar/{str(sku_id).strip()}"
    timeout_ms = int(max(5.0, float(timeout_s)) * 1000)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="zh-CN",
                )
                page = await context.new_page()
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Try to let client-side hydration mount __NEXT_DATA__ and page payload.
                try:
                    await page.wait_for_timeout(1200)
                except Exception:
                    pass
                html = await page.content()
                status = int(resp.status) if resp else 200
                await context.close()
                return status, html
            finally:
                await browser.close()
    except Exception:
        return 0, None

