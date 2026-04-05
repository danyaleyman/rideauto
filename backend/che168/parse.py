"""Extract dealer listing IDs from Che168 HTML (list pages)."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Список PC: <li ... class="... cards-li ..." infoid="..." dealerid="..." price="..." ...>
_CARDS_LI_OPEN_RE = re.compile(r"<li\b[^>]*\bcards-li\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r'\b([a-zA-Z][a-zA-Z0-9_]*)\s*=\s*"([^"]*)"')

# Relative or absolute links to /dealer/{dealer_id}/{offer_id}.html
_DEALER_LINK_RE = re.compile(
    r"(?:https?://(?:www\.)?che168\.com)?/dealer/(\d+)/(\d+)\.html",
    re.IGNORECASE,
)


def find_dealer_pairs(html: str) -> List[Tuple[str, str]]:
    """Return unique (dealer_id, offer_id) pairs in document order."""
    seen: set[Tuple[str, str]] = set()
    out: List[Tuple[str, str]] = []
    if not html:
        return out
    for m in _DEALER_LINK_RE.finditer(html):
        key = (m.group(1), m.group(2))
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


_ANCHOR_RE = re.compile(
    r'<a\b[^>]*\bhref\s*=\s*["\'](?:https?://(?:www\.)?che168\.com)?/dealer/(\d+)/(\d+)\.html[^"\']*["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def parse_cards_li_rows(html: str) -> List[Dict[str, str]]:
    """
    Разбор карточек листинга PC Che168 (атрибуты на открывающем <li>).
    Поля: infoid, dealerid, price (万元), milage, regdate, specid, carname, brandid, seriesid, publicdate, ...
    """
    rows: List[Dict[str, str]] = []
    if not html:
        return rows
    for m in _CARDS_LI_OPEN_RE.finditer(html):
        tag = m.group(0)
        attrs: Dict[str, str] = {}
        for am in _ATTR_RE.finditer(tag):
            attrs[am.group(1).lower()] = am.group(2)
        if attrs.get("infoid") and attrs.get("dealerid"):
            rows.append(attrs)
    return rows


def anchor_text_by_pairs(html: str) -> dict[Tuple[str, str], str]:
    """Map (dealer_id, offer_id) → visible link text (first non-empty)."""
    m: dict[Tuple[str, str], str] = {}
    for mo in _ANCHOR_RE.finditer(html or ""):
        key = (mo.group(1), mo.group(2))
        raw = mo.group(3) or ""
        text = " ".join(re.sub(r"<[^>]+>", " ", raw).split())
        if key not in m and text:
            m[key] = text
    return m
