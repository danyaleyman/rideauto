"""Map Che168 list rows to the same `{"data": {...}}` shape as Encar imports."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_WAN_KM_RE = re.compile(r"([\d.]+)\s*万公里")
_YM_RE = re.compile(r"(\d{4})-(\d{2})")
# Цены «8.78万»; не путать с пробегом «6.7万公里».
_PRICE_WAN_RE = re.compile(r"([\d]+(?:\.[\d]+)?)万(?!公里)")


def _utc_date_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_card_text(text: str) -> Dict[str, Any]:
    """Heuristic fields from Che168 list card title (Chinese)."""
    out: Dict[str, Any] = {}
    if not text or not text.strip():
        return out
    t = text.strip()
    m = _WAN_KM_RE.search(t)
    if m:
        try:
            out["km_age"] = int(float(m.group(1)) * 10000)
        except ValueError:
            pass
    if "未上牌" in t:
        out["year"] = ""
        out["yearMonth"] = ""
    else:
        ym = _YM_RE.search(t)
        if ym:
            out["year"] = ym.group(1)
            out["yearMonth"] = f"{ym.group(1)}{ym.group(2)}"
    prices = []
    for pm in _PRICE_WAN_RE.finditer(t):
        try:
            prices.append(float(pm.group(1)))
        except ValueError:
            continue
    if prices:
        wan = prices[0]
        out["price_cny_wan"] = wan
        out["price_cny"] = wan * 10000.0
    return out


def listing_to_car_payload(
    dealer_id: str,
    offer_id: str,
    *,
    anchor_text: str = "",
    cny_to_rub: float = 13.0,
) -> Dict[str, Any]:
    """
    Build storage document for `cars.data_json` (Encar-compatible catalog fields where possible).

    `my_price` is a rough RUB estimate from the first «…万» price on the card × `cny_to_rub` × 10000.
    """
    url = f"https://www.che168.com/dealer/{dealer_id}/{offer_id}.html"
    parsed = parse_card_text(anchor_text)
    my_price: Optional[float] = None
    if "price_cny" in parsed:
        try:
            my_price = round(float(parsed["price_cny"]) * float(cny_to_rub))
        except (TypeError, ValueError):
            my_price = None
    data: Dict[str, Any] = {
        "source": "che168",
        "che168_dealer_id": dealer_id,
        "che168_offer_id": offer_id,
        "inner_id": offer_id,
        "url": url,
        "mark": "中国二手车",
        "model": (anchor_text[:120] if anchor_text else "") or f"Che168 #{offer_id}",
        "offer_created": _utc_date_tag(),
        "created_at": _utc_date_tag(),
    }
    if my_price is not None:
        data["my_price"] = my_price
    for k in ("km_age", "year", "yearMonth", "price_cny", "price_cny_wan"):
        if k in parsed:
            data[k] = parsed[k]
    return {"data": data}


def card_li_attrs_to_payload(
    attrs: Dict[str, Any],
    *,
    cny_to_rub: float = 13.0,
    mark_fallback: str = "中国二手车",
) -> Dict[str, Any]:
    """Листинг PC: атрибуты с <li class=\"cards-li\" …>. Цена в **万元** (поле price)."""
    dealer_id = str(attrs.get("dealerid") or "").strip()
    offer_id = str(attrs.get("infoid") or "").strip()
    if not dealer_id or not offer_id:
        return {"data": {}}
    url = f"https://www.che168.com/dealer/{dealer_id}/{offer_id}.html"
    carname = str(attrs.get("carname") or "").strip()
    try:
        price_wan = float(str(attrs.get("price") or "0").strip() or 0)
    except ValueError:
        price_wan = 0.0
    price_cny = price_wan * 10000.0
    my_price = round(price_cny * float(cny_to_rub)) if price_cny > 0 else None
    regdate = str(attrs.get("regdate") or "").strip()
    year = ""
    year_month = ""
    if "/" in regdate:
        parts = regdate.split("/")
        if parts[0].isdigit() and len(parts[0]) == 4:
            year = parts[0]
            if len(parts) >= 2 and parts[1].isdigit():
                year_month = f"{parts[0]}{int(parts[1]):02d}"
    km_age: Optional[int] = None
    raw_m = str(attrs.get("milage") or attrs.get("mileage") or "").strip()
    if raw_m:
        try:
            km_age = int(float(raw_m) * 10000)
        except ValueError:
            pass
    pub = str(attrs.get("publicdate") or "").strip()
    offer_tag = pub[:10] if pub else _utc_date_tag()
    bid = attrs.get("brandid")
    sid = attrs.get("seriesid")
    spid = attrs.get("specid")
    data: Dict[str, Any] = {
        "source": "che168",
        "che168_dealer_id": dealer_id,
        "che168_offer_id": offer_id,
        "inner_id": offer_id,
        "url": url,
        "mark": mark_fallback,
        "model": carname or f"Che168 #{offer_id}",
        "offer_created": offer_tag,
        "created_at": _utc_date_tag(),
    }
    if my_price is not None:
        data["my_price"] = my_price
    if price_cny > 0:
        data["price_cny"] = price_cny
        data["price_cny_wan"] = price_wan
    if year:
        data["year"] = year
    if year_month:
        data["yearMonth"] = year_month
    if km_age is not None:
        data["km_age"] = km_age
    if bid not in (None, ""):
        data["che168_brandid"] = bid
    if sid not in (None, ""):
        data["che168_seriesid"] = sid
    if spid not in (None, "", "0"):
        data["che168_specid"] = spid
    cid = attrs.get("cid")
    pid = attrs.get("pid")
    if cid:
        data["che168_cid"] = cid
    if pid:
        data["che168_pid"] = pid
    return {"data": data}


def row_matches_filters(
    attrs: Dict[str, str],
    *,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    price_min_cny: Optional[float] = None,
    price_max_cny: Optional[float] = None,
) -> bool:
    """Фильтры после разбора (если в URL не сузили). Цена в CNY, год по regdate."""
    regdate = str(attrs.get("regdate") or "").strip()
    y: Optional[int] = None
    if "/" in regdate:
        y_s = regdate.split("/")[0]
        if y_s.isdigit():
            y = int(y_s)
    if year_min is not None and y is not None and y < year_min:
        return False
    if year_max is not None and y is not None and y > year_max:
        return False
    try:
        price_wan = float(str(attrs.get("price") or "0").strip() or 0)
    except ValueError:
        price_wan = 0.0
    cny = price_wan * 10000.0
    if price_min_cny is not None and cny > 0 and cny < price_min_cny:
        return False
    if price_max_cny is not None and cny > 0 and cny > price_max_cny:
        return False
    return True
