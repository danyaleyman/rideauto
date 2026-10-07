"""Autotrader USA: extract __NEXT_DATA__ and normalize to catalog payload."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

PARSER_SCHEMA_VERSION = "autotrader.normalized.v1"
SOURCE = "autotrader"
MILES_TO_KM = 1.609344

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def extract_next_data(html: str) -> Optional[dict]:
    if not html:
        return None
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        log.warning("autotrader: __NEXT_DATA__ JSON parse failed: %s", e)
        return None
    return data if isinstance(data, dict) else None


def eggs_state(next_data: dict) -> dict:
    pp = (next_data.get("props") or {}).get("pageProps") or {}
    eggs = pp.get("__eggsState")
    return eggs if isinstance(eggs, dict) else {}


def parse_srp_page(html: str) -> Dict[str, Any]:
    """
    Returns:
      active_ids: list[str]
      inventory: dict[str, dict]  (raw AT cards)
      total_count: int | None
      pagination_hrefs: list[{page, href}]
      build_id: str | None
    """
    nd = extract_next_data(html)
    if not nd:
        return {
            "active_ids": [],
            "inventory": {},
            "total_count": None,
            "pagination_hrefs": [],
            "build_id": None,
            "ok": False,
        }
    eggs = eggs_state(nd)
    srp = eggs.get("srp_results") or {}
    active = srp.get("activeResults") or []
    active_ids = [str(x) for x in active if x is not None and str(x).strip()]
    inv_raw = eggs.get("inventory") or {}
    inventory = {str(k): v for k, v in inv_raw.items() if isinstance(v, dict)}
    links = ((eggs.get("srp_srpPaginationLinks") or {}).get("links")) or []
    pagination = [x for x in links if isinstance(x, dict)]
    count = srp.get("count")
    try:
        total_count = int(count) if count is not None else None
    except (TypeError, ValueError):
        total_count = None
    return {
        "active_ids": active_ids,
        "inventory": inventory,
        "total_count": total_count,
        "pagination_hrefs": pagination,
        "build_id": nd.get("buildId"),
        "ok": True,
    }


def parse_vdp_page(html: str, listing_id: Optional[str] = None) -> Dict[str, Any]:
    nd = extract_next_data(html)
    if not nd:
        return {"listing": None, "listing_id": listing_id, "ok": False}
    eggs = eggs_state(nd)
    inv = eggs.get("inventory") or {}
    if not isinstance(inv, dict) or not inv:
        return {"listing": None, "listing_id": listing_id, "ok": False}
    lid = str(listing_id).strip() if listing_id else ""
    if lid and lid in inv and isinstance(inv[lid], dict):
        listing = inv[lid]
    else:
        # single-key VDP or first entry
        if lid and lid not in inv:
            # try int/str variants
            for k, v in inv.items():
                if str(k) == lid and isinstance(v, dict):
                    listing = v
                    lid = str(k)
                    break
            else:
                k0 = next(iter(inv))
                listing = inv[k0] if isinstance(inv[k0], dict) else None
                lid = str(k0)
        else:
            k0 = next(iter(inv))
            listing = inv[k0] if isinstance(inv[k0], dict) else None
            lid = str(k0)
    return {"listing": listing, "listing_id": lid, "build_id": nd.get("buildId"), "ok": listing is not None}


def _name_code(obj: Any) -> Tuple[Optional[str], Optional[str]]:
    if isinstance(obj, dict):
        name = obj.get("name")
        code = obj.get("code")
        return (
            str(name).strip() if name not in (None, "") else None,
            str(code).strip() if code not in (None, "") else None,
        )
    if obj not in (None, ""):
        return str(obj).strip(), None
    return None, None


def _safe_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def extract_image_urls_from_listing(listing: dict) -> List[str]:
    images = listing.get("images") or {}
    out: List[str] = []
    seen: set[str] = set()

    def _push(raw: Any) -> None:
        if not raw:
            return
        if isinstance(raw, dict):
            raw = raw.get("src") or raw.get("url") or raw.get("uri")
        u = str(raw).strip() if raw not in (None, "") else ""
        if u and u not in seen:
            seen.add(u)
            out.append(u)

    if isinstance(images, dict):
        sources = images.get("sources")
        if isinstance(sources, list):
            for item in sources:
                _push(item)
        # SRP cards often only expose primary when sources is empty/short
        if not out:
            _push(images.get("primary"))
    elif isinstance(images, list):
        for item in images:
            _push(item)
    return out


def extract_mileage_miles(listing: dict) -> Optional[int]:
    m = listing.get("mileage")
    if isinstance(m, dict):
        return _safe_int(m.get("value"))
    return _safe_int(m)


def extract_price_usd(listing: dict) -> Optional[float]:
    pd = listing.get("pricingDetail")
    if isinstance(pd, dict):
        for key in ("salePrice", "preFeeDerivedPrice", "msrp", "displayPrice", "incentive"):
            v = _safe_float(pd.get(key))
            if v is not None and v > 0:
                return v
    return None


def flatten_features(listing: dict) -> List[str]:
    feats = listing.get("features")
    out: List[str] = []
    seen: set[str] = set()
    if isinstance(feats, dict):
        for _bucket, items in feats.items():
            if not isinstance(items, list):
                continue
            for x in items:
                s = str(x).strip()
                if s and s not in seen:
                    seen.add(s)
                    out.append(s)
    elif isinstance(feats, list):
        for x in feats:
            s = str(x).strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return out


def car_id_for_listing(listing_id: str | int) -> str:
    return f"{SOURCE}-{listing_id}"


def normalize_listing(
    listing: dict,
    *,
    listing_id: Optional[str] = None,
    depth: str = "vdp",
) -> Dict[str, Any]:
    """
    Map Autotrader inventory card → RideAuto cars.data-shaped dict.

    depth: "srp" | "vdp"
    """
    lid = str(listing_id or listing.get("id") or "").strip()
    if not lid:
        raise ValueError("listing id required")

    make_name, make_code = _name_code(listing.get("make"))
    if not make_code:
        make_code = str(listing.get("makeCode") or "").strip() or None
    model_name, model_code = _name_code(listing.get("model"))
    if not model_code:
        model_code = str(listing.get("modelCode") or "").strip() or None
    trim_name, _trim_code = _name_code(listing.get("trim"))
    if not trim_name:
        trim_name = str(listing.get("atTrim") or "").strip() or None

    fuel_name, _ = _name_code(listing.get("fuelType"))
    drive = listing.get("driveType")
    if isinstance(drive, dict):
        drive_name = drive.get("description") or drive.get("name")
    else:
        drive_name = drive
    trans = listing.get("transmission")
    if isinstance(trans, dict):
        trans_name = trans.get("description") or trans.get("name") or trans.get("group")
    else:
        trans_name = trans

    body_type = None
    body_codes = listing.get("bodyStyleCodes") or listing.get("bodyStyles") or []
    if isinstance(body_codes, list) and body_codes:
        first = body_codes[0]
        name, code = _name_code(first)
        body_type = name or code or (str(first).strip() if first not in (None, "") else None)
    elif body_codes not in (None, ""):
        name, code = _name_code(body_codes)
        body_type = name or code

    color_obj = listing.get("color") if isinstance(listing.get("color"), dict) else {}
    color = (
        (color_obj or {}).get("exteriorColor")
        or listing.get("exteriorColorSimple")
        or (color_obj or {}).get("exteriorColorSimple")
    )

    miles = extract_mileage_miles(listing)
    km_age = int(round(miles * MILES_TO_KM)) if miles is not None else None
    price_usd = extract_price_usd(listing)
    images = extract_image_urls_from_listing(listing)

    owner = listing.get("owner") if isinstance(listing.get("owner"), dict) else {}
    loc = (owner.get("location") or {}).get("address") if isinstance(owner.get("location"), dict) else {}
    if not isinstance(loc, dict):
        loc = {}

    title = (
        listing.get("listingTitle")
        or listing.get("listingTitleLong")
        or f"{listing.get('listingType') or ''} {listing.get('year') or ''} {make_name or ''} {model_name or ''}".strip()
    )

    features_flat = flatten_features(listing)
    ranked = listing.get("rankedFeatures") if isinstance(listing.get("rankedFeatures"), dict) else {}
    specs = listing.get("specifications") if isinstance(listing.get("specifications"), dict) else {}

    car: Dict[str, Any] = {
        "source": SOURCE,
        "id": lid,
        "inner_id": lid,
        "mark": make_name,
        "model": model_name,
        "configuration": trim_name,
        "gradeName": trim_name,
        "year": _safe_int(listing.get("year")),
        "km_age": km_age,
        "mileage_miles": miles,
        "price_usd": price_usd,
        "price_on_request": price_usd is None or price_usd <= 0,
        "vin": str(listing.get("vin") or "").strip() or None,
        "images": images,
        "engine_type": fuel_name,
        "transmission_type": str(trans_name).strip() if trans_name else None,
        "drive_type": str(drive_name).strip() if drive_name else None,
        "body_type": body_type,
        "color": str(color).strip() if color else None,
        "listing_title": title,
        "listing_type": str(listing.get("listingType") or "").strip() or None,
        "stock_number": str(listing.get("stockNumber") or "").strip() or None,
        "style_id": listing.get("styleId"),
        "make_code": make_code,
        "model_code": model_code,
        "dealer_id": owner.get("id") or listing.get("ownerId") or listing.get("externalOwnerId"),
        "dealer_name": owner.get("name") or listing.get("ownerName"),
        "dealer_city": loc.get("city"),
        "dealer_state": loc.get("state"),
        "dealer_zip": loc.get("zip"),
        "dealer_address": loc.get("address1"),
        "features": features_flat,
        "features_by_group": listing.get("features") if isinstance(listing.get("features"), dict) else None,
        "ranked_features": ranked or None,
        "specifications": specs or None,
        "packages": listing.get("packages") if isinstance(listing.get("packages"), list) else None,
        "mpg_city": listing.get("mpgCity"),
        "mpg_highway": listing.get("mpgHighway"),
        "days_on_site": listing.get("daysOnSite"),
        "autotrader_depth": depth,
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "detail_url": f"https://www.autotrader.com/cars-for-sale/vehicle/{lid}",
        "_raw": {
            "source": SOURCE,
            "listing_id": lid,
            "depth": depth,
            "pricingDetail": listing.get("pricingDetail"),
            "inventory_keys": sorted(str(k) for k in listing.keys()),
        },
    }
    # drop Nones in top-level optional clutter (keep explicit falsy ints)
    return car


def normalize_listing_async_ready(listing: dict, **kwargs: Any) -> Dict[str, Any]:
    """Sync helper name aligned with che168 *_async pattern callers."""
    return normalize_listing(listing, **kwargs)
