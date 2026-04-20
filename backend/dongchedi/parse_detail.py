"""Разбор HTML карточки: встроенный JSON __NEXT_DATA__ → skuDetail."""

from __future__ import annotations

import json
import html as html_lib
import re
from typing import Any, Dict, Optional

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_SKU_DETAIL_MARK_RE = re.compile(r'"skuDetail"\s*:\s*\{', re.DOTALL)
_SKU_DETAIL_ESC_MARK_RE = re.compile(r'\\"skuDetail\\"\s*:\s*\{', re.DOTALL)
_PARAMS_CAR_ID_RE = re.compile(r"params-carIds-(\d{3,9})")

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


def _next_data_root(html: str) -> Dict[str, Any]:
    if not html:
        return {}
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return {}
    blob = m.group(1)
    try:
        root = json.loads(blob)
    except json.JSONDecodeError:
        # Иногда контент script HTML-escaped.
        try:
            root = json.loads(html_lib.unescape(blob))
        except json.JSONDecodeError:
            return {}
    return root if isinstance(root, dict) else {}


def _next_data_page_props(html: str) -> Dict[str, Any]:
    root = _next_data_root(html)
    if not root:
        return {}
    pp = (root.get("props") or {}).get("pageProps") or {}
    return pp if isinstance(pp, dict) else {}


def _extract_balanced_object(text: str, open_brace_idx: int) -> Optional[str]:
    """Return JSON object substring starting at '{' with balanced braces."""
    if open_brace_idx < 0 or open_brace_idx >= len(text) or text[open_brace_idx] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(open_brace_idx, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace_idx : i + 1]
    return None


def _sku_detail_from_raw_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Fallback parser for pages where __NEXT_DATA__ is missing or altered.
    Extracts `"skuDetail": { ... }` directly from HTML text.
    """
    if not html:
        return None
    candidates = [
        html or "",
        (html or "").replace('\\"', '"').replace("\\/", "/"),
    ]
    for cand in candidates:
        m = _SKU_DETAIL_MARK_RE.search(cand) or _SKU_DETAIL_ESC_MARK_RE.search(cand)
        if not m:
            continue
        # marker ends right after first '{' for skuDetail object
        open_idx = m.end() - 1
        blob = _extract_balanced_object(cand, open_idx)
        if not blob:
            continue
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            # Иногда объект сериализован как escaped JSON-фрагмент в JS-строке.
            try:
                obj = json.loads(blob.replace('\\"', '"').replace("\\/", "/"))
            except json.JSONDecodeError:
                continue
        if isinstance(obj, dict):
            return obj
    return None


def _find_detail_like_obj(root: Any, depth: int = 0) -> Optional[Dict[str, Any]]:
    """
    Fallback for pages where detail isn't under pageProps.skuDetail.
    Looks for dicts that resemble usedcar detail payloads.
    """
    if depth > 14 or root is None:
        return None
    if isinstance(root, dict):
        # Typical Dongchedi detail hints.
        score = 0
        if isinstance(root.get("car_info"), dict):
            score += 3
        for k in ("image_list", "head_images", "images", "car_image_list", "sku_image_list"):
            if isinstance(root.get(k), list):
                score += 2
        if any(k in root for k in ("source_sh_price", "include_tax_price", "important_text", "car_config_overview")):
            score += 1
        if score >= 3:
            return root
        # Prefer fields commonly used by Next page props.
        for key in ("skuDetail", "rawData", "detail", "detailInfo", "usedCarDetail", "carDetail"):
            if key in root:
                found = _find_detail_like_obj(root.get(key), depth + 1)
                if found:
                    return found
        for v in root.values():
            found = _find_detail_like_obj(v, depth + 1)
            if found:
                return found
    elif isinstance(root, list):
        for item in root[:200]:
            found = _find_detail_like_obj(item, depth + 1)
            if found:
                return found
    return None


def parse_sku_detail_from_html(html: str) -> Optional[Dict[str, Any]]:
    pp = _next_data_page_props(html)
    sd = pp.get("skuDetail")
    if isinstance(sd, str) and sd.strip():
        try:
            sd = json.loads(sd)
        except json.JSONDecodeError:
            sd = None
    if not isinstance(sd, dict):
        sd = _find_detail_like_obj(pp)
    if not isinstance(sd, dict):
        root = _next_data_root(html)
        if root:
            # На части версий Dongchedi detail бывает глубже, вне pageProps.
            sd = _find_detail_like_obj(root.get("props")) or _find_detail_like_obj(root)
        if not isinstance(sd, dict):
            sd = _sku_detail_from_raw_html(html)
        if not isinstance(sd, dict):
            return None
    hint = _km_hint_from_usedcar_html(html)
    if hint is not None:
        sd.setdefault("_mileage_hint_km", hint)
    cid = _PARAMS_CAR_ID_RE.search(html or "")
    if cid:
        sd.setdefault("_spec_car_id_hint", cid.group(1))
    return sd


def parse_params_raw_data_from_html(html: str) -> Optional[Dict[str, Any]]:
    """Страница /auto/params-carIds-{id} → pageProps.rawData (комплектация, МСРП, год модели)."""
    pp = _next_data_page_props(html)
    rd = pp.get("rawData")
    if isinstance(rd, dict):
        return rd
    # Fallback: структура может переехать в другие блоки.
    root = _next_data_root(html)
    hit = _find_detail_like_obj(root.get("props")) if isinstance(root, dict) else None
    if isinstance(hit, dict) and isinstance(hit.get("car_info"), dict):
        return hit
    hit2 = _find_detail_like_obj(root) if isinstance(root, dict) else None
    if isinstance(hit2, dict) and isinstance(hit2.get("car_info"), dict):
        return hit2
    return None
