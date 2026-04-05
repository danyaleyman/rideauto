"""Разбор HTML карточки: встроенный JSON __NEXT_DATA__ → skuDetail."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def parse_sku_detail_from_html(html: str) -> Optional[Dict[str, Any]]:
    if not html:
        return None
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        root = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    pp = (root.get("props") or {}).get("pageProps") or {}
    sd = pp.get("skuDetail")
    return sd if isinstance(sd, dict) else None
