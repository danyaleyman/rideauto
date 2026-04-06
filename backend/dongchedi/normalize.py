"""SKU из API + опционально skuDetail → документ для cars.data_json."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_WAN_KM_RE = re.compile(r"([\d.]+)\s*万公里")
_WAN_PRICE_RE = re.compile(r"([\d]+(?:\.[\d]+)?)\s*万")
_HP_RE = re.compile(r"(\d+)\s*马力")
_TRANSFER_CNT_RE = re.compile(r"(\d+)\s*次")
_REG_YM_RE = re.compile(r"(\d{4})年\s*(\d{1,2})\s*月")


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


def _param_pairs_from_detail(detail: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Собирает name→value из other_params / important_params карточки Dongchedi."""
    out: Dict[str, str] = {}
    if not detail or not isinstance(detail, dict):
        return out
    for key in ("other_params", "important_params"):
        raw = detail.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            val = str(item.get("value") or "").strip()
            if name and val and len(name) < 80 and len(val) < 200:
                out[name] = val
    return out


def _parse_register_year_month(s: str) -> tuple[str, str]:
    """'2019年06月' → ('2019', '201906'). Пустые строки если не распознано."""
    m = _REG_YM_RE.search(s or "")
    if not m:
        return "", ""
    y, mo = m.group(1), m.group(2).zfill(2)
    return y, f"{y}{mo}"


def _parse_horsepower_ma(s: Any) -> Optional[int]:
    m = _HP_RE.search(str(s or ""))
    if not m:
        return None
    try:
        hp = int(m.group(1))
    except ValueError:
        return None
    return hp if 20 <= hp <= 2000 else None


def _parse_transfer_times(s: str) -> Optional[int]:
    m = _TRANSFER_CNT_RE.search(s or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _displacement_cc_from_label(s: str) -> Optional[str]:
    """Только если явно в см³ (цифры ~800–8000); иначе None — текст в dongchedi_displacement_label."""
    t = str(s or "").strip().replace(" ", "")
    if not t:
        return None
    if "T" in t.upper() or t.endswith("L") or "升" in t:
        return None
    digits = re.sub(r"[^\d]", "", t)
    if not digits:
        return None
    try:
        n = int(digits)
    except ValueError:
        return None
    if 800 <= n <= 8000:
        return str(n)
    return None


def _first_nonempty_str(*vals: Any) -> str:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _deep_collect_image_urls(detail: Dict[str, Any], *, max_urls: int = 80) -> list[str]:
    """Рекурсивно вытаскивает URL картинок из skuDetail (__NEXT_DATA__): галереи часто вложены."""

    out: list[str] = []
    dup: set[str] = set()

    def looks_like_photo_url(low: str) -> bool:
        return any(
            x in low
            for x in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
                "byteimg",
                "bytecdn",
                "dcdapp",
                "dcd-cdn",
                "p3-dcd",
                "p9-dcd",
                "p6-dcd",
                "tos-cn",
                "/image",
                "img",
                "photo",
                "pic",
            )
        )

    def walk(o: Any, depth: int) -> None:
        if depth > 18 or len(out) >= max_urls:
            return
        if isinstance(o, str):
            s = o.strip()
            if len(s) < 20 or not s.startswith("http"):
                return
            low = s.lower()
            if s in dup or not looks_like_photo_url(low):
                return
            dup.add(s)
            out.append(s)
            return
        if isinstance(o, dict):
            for v in o.values():
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o[:500]:
                walk(v, depth + 1)

    walk(detail, 0)
    return out


def _image_urls_from_row_and_detail(
    row_img: str,
    detail: Optional[Dict[str, Any]],
) -> list[str]:
    out: list[str] = []
    dup: set[str] = set()

    def add(u: str) -> None:
        s = (u or "").strip()
        if s and s not in dup:
            dup.add(s)
            out.append(s)

    add(row_img)
    if not detail or not isinstance(detail, dict):
        return out
    for key in (
        "head_images",
        "image_list",
        "images",
        "sku_image_list",
        "car_image_list",
        "photo_list",
        "image_url_list",
        "car_image_info_list",
        "appearance_image_list",
        "interior_image_list",
        "space_image_list",
        "official_photo_list",
        "sku_car_image_list",
    ):
        raw = detail.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                u = _first_nonempty_str(
                    item.get("url"),
                    item.get("image"),
                    item.get("image_url"),
                    item.get("pic_url"),
                    item.get("big_url"),
                    item.get("thumb_url"),
                    item.get("cover_url"),
                )
                add(u)
    for u in _deep_collect_image_urls(detail, max_urls=100):
        add(u)
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

    ci: Dict[str, Any] = {}
    if detail and isinstance(detail.get("car_info"), dict):
        ci = detail["car_info"]

    cy = row.get("car_year")
    year = str(int(cy)) if isinstance(cy, int) else (str(cy).strip() if cy not in (None, "") else "")
    cy_ci = ci.get("year") if ci else None
    if isinstance(cy_ci, int) and 1990 <= cy_ci <= 2035:
        year = str(cy_ci)
    year_month = ""
    if year and len(year) == 4 and year.isdigit():
        year_month = f"{year}01"

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
            ci.get("body_color"),
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

    row_city = _first_nonempty_str(row.get("car_source_city_name"))
    if row_city:
        data.setdefault("city", row_city)
    try:
        tc = row.get("transfer_cnt")
        if tc is not None and str(tc).strip() != "":
            data["transfer_count"] = int(tc)
    except (TypeError, ValueError):
        pass

    car_name_row = _first_nonempty_str(row.get("car_name"))
    if car_name_row:
        data.setdefault("configuration", car_name_row)
        data.setdefault("gradeName", car_name_row)

    params = _param_pairs_from_detail(detail)
    if params:
        pv = params.get("车源地") or params.get("上牌地")
        if pv:
            data["city"] = pv
        pv = params.get("过户次数")
        if pv:
            pt = _parse_transfer_times(pv)
            if pt is not None:
                data["transfer_count"] = pt
        pv = params.get("上牌时间")
        if pv:
            y_reg, ym_reg = _parse_register_year_month(pv)
            if y_reg:
                data["year"] = y_reg
            if ym_reg:
                data["yearMonth"] = ym_reg
        pv = params.get("排量")
        if pv:
            cc = _displacement_cc_from_label(pv)
            if cc:
                data["displacement"] = cc
            elif not data.get("displacement"):
                data["dongchedi_displacement_label"] = str(pv).strip()
        pv = params.get("变速箱")
        if pv and not data.get("transmission_type"):
            data["transmission_type"] = str(pv).strip()
        pv = params.get("车身颜色")
        if pv:
            data["color"] = str(pv).strip()
        pv = params.get("内饰颜色")
        if pv:
            data["interior_color"] = str(pv).strip()

    itext = _first_nonempty_str((detail or {}).get("important_text")) if detail else ""
    if itext:
        data["dongchedi_summary"] = itext

    cc_over = (detail or {}).get("car_config_overview") if detail else None
    if isinstance(cc_over, dict):
        cn = _first_nonempty_str(cc_over.get("car_name"))
        if cn:
            data["configuration"] = cn
            data["gradeName"] = cn
        man = cc_over.get("manipulation")
        if isinstance(man, dict):
            df = _first_nonempty_str(man.get("driver_form"))
            if df:
                data["drive_type"] = df
        powd = cc_over.get("power")
        if isinstance(powd, dict):
            hpv = _parse_horsepower_ma(powd.get("horsepower"))
            if hpv is not None:
                data["hp"] = hpv
            if not data.get("engine_type"):
                fu = _first_nonempty_str(powd.get("fuel_form"))
                if fu:
                    data["engine_type"] = fu
            if not data.get("transmission_type"):
                gbd = _first_nonempty_str(powd.get("gearbox_description"))
                if gbd:
                    data["transmission_type"] = gbd
            if not data.get("displacement") and not data.get("dongchedi_displacement_label"):
                cap = _first_nonempty_str(powd.get("capacity"))
                if cap:
                    cc2 = _displacement_cc_from_label(cap)
                    if cc2:
                        data["displacement"] = cc2
                    else:
                        data["dongchedi_displacement_label"] = cap

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
