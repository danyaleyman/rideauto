"""SKU из API + опционально skuDetail → документ для cars.data_json."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_WAN_KM_RE = re.compile(r"([\d.]+)\s*万公里")
_WAN_PRICE_RE = re.compile(r"([\d]+(?:\.[\d]+)?)\s*万")


def _utc_date_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fen_to_cny(fen: Any) -> Optional[float]:
    try:
        v = int(fen)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v / 100.0


def _parse_wan_price_text(s: str) -> Optional[float]:
    if not s or not str(s).strip():
        return None
    m = _WAN_PRICE_RE.search(str(s))
    if not m:
        return None
    try:
        return float(m.group(1)) * 10000.0
    except ValueError:
        return None


def _km_from_mileage_str(raw: str) -> Optional[int]:
    if not raw:
        return None
    m = _WAN_KM_RE.search(raw)
    if not m:
        return None
    try:
        return int(float(m.group(1)) * 10000)
    except ValueError:
        return None


def _first_nonempty_str(*vals: Any) -> str:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _image_urls_from_row_and_detail(
    row_img: str,
    detail: Optional[Dict[str, Any]],
) -> list[str]:
    out: list[str] = []
    if row_img:
        out.append(row_img)
    if not detail or not isinstance(detail, dict):
        return out
    for key in (
        "image_list",
        "images",
        "sku_image_list",
        "car_image_list",
        "photo_list",
        "image_url_list",
    ):
        raw = detail.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str):
                u = item.strip()
                if u and u not in out:
                    out.append(u)
            elif isinstance(item, dict):
                u = _first_nonempty_str(
                    item.get("url"),
                    item.get("image"),
                    item.get("image_url"),
                    item.get("pic_url"),
                )
                if u and u not in out:
                    out.append(u)
    return out


def sku_row_to_payload(
    row: Dict[str, Any],
    *,
    detail: Optional[Dict[str, Any]] = None,
    cny_to_rub: float = 13.0,
) -> Dict[str, Any]:
    """
    row — элемент search_sh_sku_info_list.
    detail — объект skuDetail из __NEXT_DATA__ (опционально, для цены в CNY).
    """
    sku_id = row.get("sku_id")
    if sku_id is None:
        return {"data": {}}
    sid = str(sku_id).strip()
    if not sid:
        return {"data": {}}

    title = str(row.get("title") or "").strip()
    brand_name = str(row.get("brand_name") or "").strip()
    series_name = str(row.get("series_name") or "").strip()
    mark = brand_name or "中国二手车"
    model = title or f"{series_name} {row.get('car_name') or ''}".strip() or f"Dongchedi #{sid}"

    cy = row.get("car_year")
    year = str(int(cy)) if isinstance(cy, int) else (str(cy).strip() if cy not in (None, "") else "")
    year_month = ""
    if year and len(year) == 4 and year.isdigit():
        year_month = f"{year}01"

    ci: Dict[str, Any] = {}
    if detail and isinstance(detail.get("car_info"), dict):
        ci = detail["car_info"]

    km_age = _km_from_mileage_str(str(row.get("car_mileage") or ""))
    if km_age is None and ci:
        km_age = _km_from_mileage_str(str(ci.get("mileage") or ""))

    img = str(row.get("image") or "").strip()
    urls = _image_urls_from_row_and_detail(img, detail)
    images_json = json.dumps(urls, ensure_ascii=False) if urls else None

    price_cny: Optional[float] = None
    if detail:
        price_cny = _fen_to_cny(detail.get("source_sh_price"))
        if price_cny is None:
            price_cny = _parse_wan_price_text(str(detail.get("include_tax_price") or ""))
        if price_cny is None:
            price_cny = _parse_wan_price_text(str(detail.get("offical_price") or ""))

    my_price: Optional[float] = None
    if price_cny is not None and price_cny > 0:
        my_price = round(float(price_cny) * float(cny_to_rub))

    url = f"https://www.dongchedi.com/usedcar/{sid}"

    data: Dict[str, Any] = {
        "source": "dongchedi",
        "dongchedi_sku_id": sid,
        "inner_id": sid,
        "url": url,
        "mark": mark,
        "model": model,
        "offer_created": _utc_date_tag(),
        "created_at": _utc_date_tag(),
    }
    if year:
        data["year"] = year
    if year_month:
        data["yearMonth"] = year_month
    if km_age is not None:
        data["km_age"] = km_age
    if my_price is not None:
        data["my_price"] = my_price
    if price_cny is not None and price_cny > 0:
        data["price_cny"] = price_cny
    if images_json:
        data["images"] = images_json
    if row.get("series_id") is not None:
        data["dongchedi_series_id"] = row.get("series_id")
    if row.get("brand_id") is not None:
        data["dongchedi_brand_id"] = row.get("brand_id")
    if series_name:
        data["dongchedi_series_name"] = series_name

    if ci:
        col = _first_nonempty_str(
            ci.get("color"),
            ci.get("car_color"),
            ci.get("exterior_color_name"),
            ci.get("exterior_color"),
        )
        if col:
            data["color"] = col
        trans = _first_nonempty_str(
            ci.get("transmission"),
            ci.get("gear_type"),
            ci.get("gearbox"),
            ci.get("gearbox_type"),
        )
        if trans:
            data["transmission_type"] = trans
        fuel = _first_nonempty_str(
            ci.get("fuel_type"),
            ci.get("fuel"),
            ci.get("energy_type"),
            ci.get("engine_type"),
        )
        if fuel:
            data["engine_type"] = fuel
        disp = _first_nonempty_str(ci.get("displacement"), ci.get("liter"))
        if disp:
            data["displacement"] = disp
        vin = _first_nonempty_str(ci.get("vin"))
        if vin:
            data["vin"] = vin
        city = _first_nonempty_str(ci.get("city_name"), ci.get("city"))
        if city:
            data["city"] = city

    return {"data": data}


def row_matches_filters(
    row: Dict[str, Any],
    *,
    series_id: Optional[int] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    price_min_cny: Optional[float] = None,
    price_max_cny: Optional[float] = None,
    price_cny: Optional[float] = None,
) -> bool:
    if series_id is not None:
        try:
            if int(row.get("series_id") or 0) != int(series_id):
                return False
        except (TypeError, ValueError):
            return False
    cy = row.get("car_year")
    y: Optional[int] = None
    if isinstance(cy, int):
        y = cy
    elif cy is not None and str(cy).isdigit():
        y = int(str(cy))
    if year_min is not None and y is not None and y < year_min:
        return False
    if year_max is not None and y is not None and y > year_max:
        return False
    if price_cny is not None and price_cny > 0:
        if price_min_cny is not None and price_cny < price_min_cny:
            return False
        if price_max_cny is not None and price_cny > price_max_cny:
            return False
    return True
