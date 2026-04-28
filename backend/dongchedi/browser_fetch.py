"""Browser helpers for Dongchedi anti-bot fallback."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional, Tuple


_PLAYWRIGHT_UNAVAILABLE = False


def _cookie_header_to_context_cookies(cookie_header: Optional[str]) -> list[Dict[str, Any]]:
    s = str(cookie_header or "").strip()
    if not s:
        return []
    out: list[Dict[str, Any]] = []
    for part in s.split(";"):
        token = part.strip()
        if not token or "=" not in token:
            continue
        name, value = token.split("=", 1)
        n = name.strip()
        if not n:
            continue
        out.append({"name": n, "value": value.strip(), "domain": ".dongchedi.com", "path": "/"})
    return out


@asynccontextmanager
async def _open_context(
    *,
    user_data_dir: Optional[str],
    user_agent: Optional[str],
) -> AsyncIterator[Any]:
    global _PLAYWRIGHT_UNAVAILABLE
    if _PLAYWRIGHT_UNAVAILABLE:
        yield None
        return
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception:
        _PLAYWRIGHT_UNAVAILABLE = True
        yield None
        return
    async with async_playwright() as p:
        browser = None
        context = None
        try:
            if user_data_dir:
                udd = str(Path(user_data_dir).resolve())
                launch_kwargs: Dict[str, Any] = {
                    "headless": True,
                    "locale": "zh-CN",
                }
                if user_agent:
                    launch_kwargs["user_agent"] = user_agent
                context = await p.chromium.launch_persistent_context(
                    udd,
                    **launch_kwargs,
                )
            else:
                browser = await p.chromium.launch(headless=True)
                kwargs: Dict[str, Any] = {"locale": "zh-CN"}
                if user_agent:
                    kwargs["user_agent"] = user_agent
                context = await browser.new_context(**kwargs)
            yield context
        finally:
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()


async def fetch_usedcar_html_playwright(
    sku_id: str,
    *,
    timeout_s: float = 25.0,
    user_data_dir: Optional[str] = None,
    user_agent: Optional[str] = None,
    cookie_header: Optional[str] = None,
) -> Tuple[int, Optional[str]]:
    url = f"https://www.dongchedi.com/usedcar/{str(sku_id).strip()}"
    timeout_ms = int(max(5.0, float(timeout_s)) * 1000)
    try:
        async with _open_context(user_data_dir=user_data_dir, user_agent=user_agent) as context:
            if context is None:
                return 0, None
            cookies = _cookie_header_to_context_cookies(cookie_header)
            if cookies:
                try:
                    await context.add_cookies(cookies)
                except Exception:
                    pass
            page = await context.new_page()
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                await page.wait_for_timeout(1200)
            except Exception:
                pass
            html = await page.content()
            status = int(resp.status) if resp else 200
            return status, html
    except Exception:
        return 0, None


async def fetch_sku_list_playwright(
    *,
    page: int,
    limit: int,
    brand_id: Optional[str] = None,
    sh_city_name: Optional[str] = None,
    age_range: Optional[str] = None,
    timeout_s: float = 25.0,
    user_data_dir: Optional[str] = None,
    user_agent: Optional[str] = None,
    cookie_header: Optional[str] = None,
) -> Tuple[int, Optional[Dict[str, Any]]]:
    timeout_ms = int(max(5.0, float(timeout_s)) * 1000)
    form: Dict[str, str] = {
        "page": str(max(1, int(page))),
        "limit": str(max(1, min(100, int(limit)))),
    }
    if brand_id is not None and str(brand_id).strip():
        form["brand"] = str(brand_id).strip()
    if sh_city_name is not None and str(sh_city_name).strip():
        form["sh_city_name"] = str(sh_city_name).strip()
    if age_range is not None and str(age_range).strip():
        form["age_range"] = str(age_range).strip()
    url = "https://www.dongchedi.com/motor/pc/sh/sh_sku_list?aid=1839&app_name=auto_web_pc"
    warmup_candidates = [
        "https://www.dongchedi.com/",
        "https://www.dongchedi.com/usedcar",
    ]
    script = """
        async ({ url, form }) => {
          const body = new URLSearchParams(form).toString();
          const r = await fetch(url, {
            method: "POST",
            headers: { "content-type": "application/x-www-form-urlencoded; charset=UTF-8" },
            credentials: "include",
            body,
          });
          let payload = null;
          try { payload = await r.json(); } catch (_) { payload = null; }
          return { status: r.status, payload };
        }
    """
    try:
        async with _open_context(user_data_dir=user_data_dir, user_agent=user_agent) as context:
            if context is None:
                return 0, None
            cookies = _cookie_header_to_context_cookies(cookie_header)
            if cookies:
                try:
                    await context.add_cookies(cookies)
                except Exception:
                    pass
            page_obj = await context.new_page()
            warmed = False
            for wu in warmup_candidates:
                try:
                    await page_obj.goto(wu, wait_until="domcontentloaded", timeout=timeout_ms)
                    warmed = True
                    break
                except Exception:
                    continue
            if not warmed:
                return 0, None
            await page_obj.wait_for_timeout(600)
            out = await page_obj.evaluate(script, {"url": url, "form": form})
            if not isinstance(out, dict):
                return 0, None
            status = int(out.get("status") or 0)
            payload = out.get("payload")
            if not isinstance(payload, dict):
                return status, None
            return status, payload
    except Exception:
        return 0, None


async def build_cookie_header_playwright(
    *,
    user_data_dir: Optional[str] = None,
    user_agent: Optional[str] = None,
    warmup_url: str = "https://www.dongchedi.com/",
    timeout_s: float = 25.0,
    cookie_header: Optional[str] = None,
) -> Optional[str]:
    timeout_ms = int(max(5.0, float(timeout_s)) * 1000)
    try:
        async with _open_context(user_data_dir=user_data_dir, user_agent=user_agent) as context:
            if context is None:
                return None
            cookies_seed = _cookie_header_to_context_cookies(cookie_header)
            if cookies_seed:
                try:
                    await context.add_cookies(cookies_seed)
                except Exception:
                    pass
            page = await context.new_page()
            warmup_candidates = [warmup_url, "https://www.dongchedi.com/usedcar"]
            warmed = False
            for wu in warmup_candidates:
                try:
                    await page.goto(wu, wait_until="domcontentloaded", timeout=timeout_ms)
                    warmed = True
                    break
                except Exception:
                    continue
            if not warmed:
                return None
            await page.wait_for_timeout(500)
            cookies = await context.cookies("https://www.dongchedi.com")
            parts = []
            for c in cookies:
                n = str(c.get("name") or "").strip()
                v = str(c.get("value") or "")
                if not n:
                    continue
                parts.append(f"{n}={v}")
            return "; ".join(parts) if parts else None
    except Exception:
        return None

