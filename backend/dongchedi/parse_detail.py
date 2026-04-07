"""Разбор HTML карточки: встроенный JSON __NEXT_DATA__ → skuDetail."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

_KM_HTML_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"【\s*行驶里程\s*】\s*([\d.]+)\s*万\s*公里"),
    re.compile(r"行驶里程\s*[:：]\s*([\d.]+)\s*万\s*公里"),
    re.compile(r"(?:里\s*程|行驶里程)\s*[\]】]\s*([\d.]+)\s*万\s*公里"),
    re.compile(r"([\d.]+)\s*万\s*公里"),
)


def _km_hint_from_usedcar_html(html: str) -> Optional[int]:
    """Пробег из текста страницы, если в skuDetail нет структурированного поля."""
    if not html or len(html) < 80:
        return None
    for rx in _KM_HTML_RES:
        m = rx.search(html)
        if not m:
            continue
        try:
            km = int(float(m.group(1)) * 10000)
        except ValueError:
            continue
        if 500 <= km <= 2_000_000:
            return km
    return None


def _next_data_page_props(html: str) -> Dict[str, Any]:
    if not html:
        return {}
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return {}
    try:
        root = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}
    pp = (root.get("props") or {}).get("pageProps") or {}
    return pp if isinstance(pp, dict) else {}


def parse_sku_detail_from_html(html: str) -> Optional[Dict[str, Any]]:
    pp = _next_data_page_props(html)
    sd = pp.get("skuDetail")
    if not isinstance(sd, dict):
        return None
    hint = _km_hint_from_usedcar_html(html)
    if hint is not None:
        sd.setdefault("_mileage_hint_km", hint)
    return sd


def parse_params_raw_data_from_html(html: str) -> Optional[Dict[str, Any]]:
    """Страница /auto/params-carIds-{id} → pageProps.rawData (комплектация, МСРП, год модели)."""
    pp = _next_data_page_props(html)
    rd = pp.get("rawData")
    return rd if isinstance(rd, dict) else None
