"""Построение URL листинга PC Che168 (?page=N)."""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote


def build_list_page_url(
    *,
    area: str = "china",
    brand_slug: Optional[str] = None,
    series_slug: Optional[str] = None,
    list_path: Optional[str] = None,
    page: int = 1,
) -> str:
    """
    - Национальный каталог: /china/list/?page=1
    - Марка: /china/{brand}/?page=1 (slug латиницей, напр. dazhong, baoma)
    - Марка + серия: /china/{brand}/{series}/?page=1
    - Полный путь из браузера: list_path=/china/beiqixinnengyuan/a3_5msdgscncgpi1ltocsp1ex/
    """
    base = "https://www.che168.com"
    p = max(1, int(page))
    if list_path:
        path = list_path.strip()
        if not path.startswith("/"):
            path = "/" + path
        if not path.endswith("/"):
            path += "/"
        return f"{base}{path}?page={p}"
    a = (area or "china").strip().strip("/")
    if not brand_slug and not series_slug:
        return f"{base}/{a}/list/?page={p}"
    b = (brand_slug or "").strip().strip("/")
    if not b:
        return f"{base}/{a}/list/?page={p}"
    s = (series_slug or "").strip().strip("/")
    if s:
        return f"{base}/{a}/{quote(b)}/{quote(s)}/?page={p}"
    return f"{base}/{a}/{quote(b)}/?page={p}"
