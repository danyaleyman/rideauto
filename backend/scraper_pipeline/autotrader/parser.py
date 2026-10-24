"""Autotrader USA: extract __NEXT_DATA__ and normalize to catalog payload."""

from __future__ import annotations

import html as html_module
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

PARSER_SCHEMA_VERSION = "autotrader.normalized.v2"
SOURCE = "autotrader"
MILES_TO_KM = 1.609344

# "2.0L", "1.6 L Turbo", "3.5-Liter V6"
_LITERS_RE = re.compile(
    r"(?P<liters>\d+(?:[.,]\d+)?)\s*(?:L|LITER|LITRE)\b",
    re.IGNORECASE,
)
# "300 HP", "250 Horsepower", "180 hp"
_HP_RE = re.compile(
    r"(?P<hp>\d{2,4})\s*(?:HP|BHP|PS|HORSEPOWER)\b",
    re.IGNORECASE,
)

# Tolerant: attributes order/quotes vary (nonce, data-nscript), attrs may be single-quoted.
_NEXT_DATA_RE = re.compile(
    r"<script[^>]*\bid=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script\s*>",
    re.DOTALL | re.IGNORECASE,
)
_JSON_LD_RE = re.compile(
    r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script\s*>",
    re.DOTALL | re.IGNORECASE,
)

# «Карточка снята/продана» — парсить нечего, повторять бессмысленно.
_UNAVAILABLE_MARKERS = (
    "no longer available",
    "this listing is not available",
    "listing not found",
    "vehicle is no longer",
    "has been removed",
    "page unavailable",
    "we're sorry",
)

# Веса качества извлечения (попадают в stats: видно, какой путь парсинга работает).
VDP_EXTRACT_EGGS = "eggs"
VDP_EXTRACT_PAGEPROPS = "pageProps"
VDP_EXTRACT_JSONLD = "jsonld"


def _json_loads_tolerant(raw: str) -> Optional[dict]:
    """JSON с Next может прийти с HTML-экранированием или `\\/script` внутри строк."""
    text = (raw or "").strip()
    if not text:
        return None
    for candidate in (
        text,
        text.replace("<\\/script", "</script").replace("\\u003c", "<").replace("\\u003e", ">"),
        html_module.unescape(text),
    ):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return data if isinstance(data, dict) else None
    return None


def extract_next_data(html: str) -> Optional[dict]:
    if not html:
        return None
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    data = _json_loads_tolerant(m.group(1))
    if data is None:
        log.warning("autotrader: __NEXT_DATA__ JSON parse failed (len=%s)", len(m.group(1)))
    return data


def extract_json_ld(html: str) -> List[dict]:
    """Все ld+json объекты (Vehicle/Car/Product/Offer) — резервный путь для VDP."""
    out: List[dict] = []
    if not html:
        return out
    for m in _JSON_LD_RE.finditer(html):
        blob = _json_loads_tolerant(m.group(1))
        if blob:
            out.append(blob)
    return out


def is_page_unavailable(html: str) -> bool:
    """True для «снято с продажи»: страница валидна, но карточки больше нет."""
    if not html:
        return False
    low = html.lower()
    if not any(m in low for m in _UNAVAILABLE_MARKERS):
        return False
    # Маркер может встретиться в тексте живой карточки («no longer available» в блоке Carfax).
    nd = extract_next_data(html)
    inv = (eggs_state(nd).get("inventory") if nd else None) or {}
    return not isinstance(inv, dict) or not inv


def eggs_state(next_data: dict) -> dict:
    pp = (next_data.get("props") or {}).get("pageProps") or {}
    eggs = pp.get("__eggsState")
    return eggs if isinstance(eggs, dict) else {}


def _ids_from_any(item: Any) -> List[str]:
    """activeResults бывает списком id, списком dict или dict{id: card}."""
    out: List[str] = []
    if isinstance(item, dict):
        for k, v in item.items():
            if isinstance(v, dict):
                lid = v.get("id") or v.get("listingId") or k
            else:
                lid = v if v not in (None, "") else k
            s = str(lid).strip()
            if s:
                out.append(s)
        return out
    if isinstance(item, list):
        for x in item:
            if isinstance(x, dict):
                lid = x.get("id") or x.get("listingId") or x.get("listing_id")
                s = str(lid).strip() if lid not in (None, "") else ""
            else:
                s = str(x).strip() if x not in (None, "") else ""
            if s:
                out.append(s)
    return out


def parse_srp_page(html: str) -> Dict[str, Any]:
    """
    Returns:
      active_ids: list[str]
      inventory: dict[str, dict]  (raw AT cards)
      total_count: int | None
      pagination_hrefs: list[{page, href}]
      build_id: str | None
      next_page_url: str | None  (реальная ссылка следующей страницы)
    """
    nd = extract_next_data(html)
    if not nd:
        return {
            "active_ids": [],
            "inventory": {},
            "total_count": None,
            "pagination_hrefs": [],
            "next_page_url": None,
            "build_id": None,
            "ok": False,
        }
    eggs = eggs_state(nd)
    srp = eggs.get("srp_results") or {}
    inv_raw = eggs.get("inventory") or {}
    inventory = {str(k): v for k, v in inv_raw.items() if isinstance(v, dict)} if isinstance(inv_raw, dict) else {}

    active_ids = _ids_from_any(srp.get("activeResults"))
    if not active_ids:
        # Резерв: srp_results.listings / results / inventory как источник id.
        for alt_key in ("listings", "results", "items", "vehicles"):
            active_ids = _ids_from_any(srp.get(alt_key))
            if active_ids:
                break
    if not active_ids and inventory:
        active_ids = list(inventory.keys())
    # Порядок важен (SRP-сортировка), но дубликаты не нужны.
    seen: set[str] = set()
    ordered: List[str] = []
    for lid in active_ids:
        if lid not in seen:
            seen.add(lid)
            ordered.append(lid)
    active_ids = ordered

    links = ((eggs.get("srp_srpPaginationLinks") or {}).get("links")) or []
    pagination = [x for x in links if isinstance(x, dict)] if isinstance(links, list) else []
    next_url: Optional[str] = None
    for link in pagination:
        rel = str(link.get("rel") or link.get("name") or "").lower()
        if rel in ("next", "nextpage", "next-page"):
            next_url = str(link.get("href") or link.get("url") or "").strip() or None
            break
    if not next_url:
        for link in pagination:
            label = str(link.get("text") or link.get("label") or "").strip().lower()
            if label in ("next", "next page", "›", "»"):
                next_url = str(link.get("href") or link.get("url") or "").strip() or None
                break

    count = srp.get("count")
    if count is None:
        count = srp.get("totalCount") or srp.get("total_count")
    try:
        total_count = int(count) if count is not None else None
    except (TypeError, ValueError):
        total_count = None
    return {
        "active_ids": active_ids,
        "inventory": inventory,
        "total_count": total_count,
        "pagination_hrefs": pagination,
        "next_page_url": next_url,
        "build_id": nd.get("buildId"),
        # ok = страница реально SRP (есть инвентарь), даже если activeResults пуст (конец выдачи).
        "ok": bool(nd) and (bool(inventory) or bool(active_ids) or total_count is not None),
    }


def _inventory_from_next_data(nd: dict) -> Dict[str, Any]:
    """Инвентарь VDP лежит либо в __eggsState, либо прямо в pageProps (варианты сборок)."""
    pp = (nd.get("props") or {}).get("pageProps") or {}
    for node in (eggs_state(nd).get("inventory"), pp.get("inventory")):
        if isinstance(node, dict) and node:
            return {str(k): v for k, v in node.items() if isinstance(v, dict)}
    return {}


def _listing_from_json_ld(blobs: List[dict], listing_id: Optional[str]) -> Optional[dict]:
    """Собираем минимальный AT-подобный listing из schema.org (последний рубеж парсинга)."""
    for blob in blobs:
        nodes: List[dict] = []
        if isinstance(blob.get("@graph"), list):
            nodes.extend(x for x in blob["@graph"] if isinstance(x, dict))
        nodes.append(blob)
        for node in nodes:
            ntype = node.get("@type")
            types = ntype if isinstance(ntype, list) else [ntype]
            if not any(str(t).lower() in ("vehicle", "car", "product", "individualproduct") for t in types):
                continue
            offers = node.get("offers") if isinstance(node.get("offers"), dict) else {}
            price = offers.get("price") or offers.get("lowPrice") or node.get("price")
            images_raw = node.get("image")
            if isinstance(images_raw, str):
                images_raw = [images_raw]
            listing: Dict[str, Any] = {
                "id": str(listing_id or node.get("sku") or node.get("productID") or "").strip() or None,
                "vin": node.get("vehicleIdentificationNumber") or node.get("sku"),
                "year": node.get("vehicleModelDate") or node.get("modelDate") or node.get("productionDate"),
                "make": node.get("brand") if isinstance(node.get("brand"), dict) else {"name": node.get("brand")},
                "model": {"name": node.get("model")},
                "trim": node.get("vehicleConfiguration") or node.get("name"),
                "mileage": {"value": (node.get("mileageFromOdometer") or {}).get("value")
                            if isinstance(node.get("mileageFromOdometer"), dict)
                            else node.get("mileageFromOdometer")},
                "pricingDetail": {"salePrice": price, "displayPrice": price},
                "images": {"sources": [{"src": u} for u in (images_raw or []) if u]},
                "listingTitle": node.get("name"),
                "engine": {"name": node.get("vehicleEngine", {}).get("name") if isinstance(node.get("vehicleEngine"), dict) else None},
                "color": {"exteriorColor": node.get("color")},
                "bodyStyleCodes": [node.get("bodyType")] if node.get("bodyType") else [],
                "_jsonld": True,
            }
            if listing["id"] or listing["vin"]:
                return listing
    return None


def parse_vdp_page(html: str, listing_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Разбор VDP. Пути (по приоритету):
      1. __NEXT_DATA__ → __eggsState.inventory / pageProps.inventory
      2. schema.org ld+json (Vehicle/Car/Product)
    Дополнительно возвращает extract_path и unavailable (снято с продажи → ретраить бессмысленно).
    """
    lid = str(listing_id).strip() if listing_id else ""
    nd = extract_next_data(html)
    inventory: Dict[str, Any] = _inventory_from_next_data(nd) if nd else {}
    listing: Optional[dict] = None
    extract_path: Optional[str] = None
    if inventory:
        if lid and lid in inventory:
            listing = inventory[lid]
        else:
            for k, v in inventory.items():
                if str(k) == lid:
                    listing = v
                    lid = str(k)
                    break
            else:
                k0 = next(iter(inventory))
                listing = inventory[k0]
                lid = str(k0) if not lid else lid
        if isinstance(listing, dict):
            extract_path = VDP_EXTRACT_EGGS if eggs_state(nd or {}).get("inventory") else VDP_EXTRACT_PAGEPROPS
        else:
            listing = None

    if listing is None:
        listing = _listing_from_json_ld(extract_json_ld(html), listing_id)
        if listing is not None:
            extract_path = VDP_EXTRACT_JSONLD
            if not lid and listing.get("id"):
                lid = str(listing["id"])

    unavailable = is_page_unavailable(html)
    return {
        "listing": listing,
        "listing_id": lid or None,
        "build_id": (nd or {}).get("buildId"),
        "ok": listing is not None,
        "extract_path": extract_path,
        "unavailable": bool(unavailable and listing is None),
        "has_next_data": nd is not None,
    }


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


_SRCSET_SPLIT_RE = re.compile(r"\s*,\s*")


def _push_image(out: List[str], seen: set[str], raw: Any) -> None:
    """Одно значение бывает строкой, dict{src|url|uri}, srcset-строкой или списком."""
    if not raw:
        return
    if isinstance(raw, (list, tuple)):
        for item in raw:
            _push_image(out, seen, item)
        return
    if isinstance(raw, dict):
        for key in ("src", "url", "uri", "href", "large", "medium", "small"):
            if raw.get(key):
                _push_image(out, seen, raw[key])
        srcset = raw.get("srcset")
        if isinstance(srcset, str) and srcset:
            _push_image(out, seen, srcset)
        return
    s = str(raw).strip()
    if not s:
        return
    if s.startswith(("http://", "https://", "//")):
        u = ("https:" + s) if s.startswith("//") else s
        if u not in seen:
            seen.add(u)
            out.append(u)
        return
    # "url1 1x, url2 2x" / "url1 320w, url2 640w"
    if "," in s and (" " in s or s.count(",") >= 1):
        for part in _SRCSET_SPLIT_RE.split(s):
            token = part.strip().split(" ")[0].strip()
            if token.startswith(("http://", "https://", "//")):
                _push_image(out, seen, token)


def extract_image_urls_from_listing(listing: dict) -> List[str]:
    images = listing.get("images") or {}
    out: List[str] = []
    seen: set[str] = set()
    if isinstance(images, dict):
        _push_image(out, seen, images.get("sources"))
        if not out:
            _push_image(out, seen, images.get("primary"))
            _push_image(out, seen, images.get("image"))
    elif isinstance(images, list):
        _push_image(out, seen, images)
    if not out:
        # Иногда галерея живёт отдельно от images (VDP-варианты сборок).
        _push_image(out, seen, listing.get("photos") or listing.get("photoUrls"))
    return out


def extract_mileage_miles(listing: dict) -> Optional[int]:
    m = listing.get("mileage")
    if isinstance(m, dict):
        v = _safe_int(m.get("value"))
        if v is not None:
            return v
        return _safe_int(m.get("miles") or m.get("mileage"))
    v = _safe_int(m)
    if v is not None:
        return v
    specs = listing.get("specifications") if isinstance(listing.get("specifications"), dict) else {}
    node = specs.get("mileage")
    if isinstance(node, dict):
        return _safe_int(node.get("value"))
    return _safe_int(node)


def extract_price_usd(listing: dict) -> Optional[float]:
    pd = listing.get("pricingDetail")
    if isinstance(pd, dict):
        # Порядок = приоритет реальной цены продажи (msrp — последний рубеж).
        for key in (
            "salePrice",
            "internetPrice",
            "askingPrice",
            "listPrice",
            "price",
            "preFeeDerivedPrice",
            "displayPrice",
            "incentive",
            "msrp",
        ):
            v = _safe_float(pd.get(key))
            if v is not None and v > 0:
                return v
    for key in ("salePrice", "internetPrice", "askingPrice", "listPrice", "price"):
        v = _safe_float(listing.get(key))
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


def _liters_to_cc(liters: float) -> Optional[int]:
    if liters <= 0:
        return None
    # Car engines: ~0.6–8.0 L. Values >= 30 are already cm³.
    if liters >= 30:
        cc = int(round(liters))
    else:
        cc = int(round(liters * 1000))
    return cc if cc > 0 else None


def _parse_liters_token(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        v = float(raw)
        return v if v > 0 else None
    s = str(raw).strip().replace(",", ".")
    if not s:
        return None
    m = _LITERS_RE.search(s)
    if m:
        try:
            return float(m.group("liters").replace(",", "."))
        except ValueError:
            return None
    try:
        v = float("".join(ch for ch in s if ch.isdigit() or ch == "."))
        return v if v > 0 else None
    except ValueError:
        return None


def extract_displacement_cc(listing: dict) -> Tuple[Optional[int], Optional[str]]:
    """
    Autotrader usually exposes displacementUOM in liters (e.g. 1.6).
    Also scrape engine description / specs for «2.0L».
    Returns (cc, human label like '1.6 L').
    """
    candidates: List[Any] = [
        listing.get("displacementUOM"),
        listing.get("displacement"),
        listing.get("displacementLiter"),
        listing.get("engineSize"),
        listing.get("engine_size"),
        listing.get("engineDisplacement"),
        listing.get("engineDescription"),
    ]
    eng = listing.get("engine")
    if isinstance(eng, dict):
        candidates.extend(
            [
                eng.get("displacement"),
                eng.get("displacementUOM"),
                eng.get("displacementLiter"),
                eng.get("size"),
                eng.get("sizeLitres"),
                eng.get("liters"),
                eng.get("name"),
                eng.get("description"),
            ]
        )
    specs = listing.get("specifications") if isinstance(listing.get("specifications"), dict) else {}
    for key in (
        "engineDescription",
        "engine",
        "engineSize",
        "engineDisplacement",
        "displacement",
        "displacementUOM",
    ):
        node = specs.get(key)
        if isinstance(node, dict):
            candidates.append(node.get("value") or node.get("label"))
        elif node not in (None, ""):
            candidates.append(node)

    for raw in candidates:
        liters = _parse_liters_token(raw)
        if liters is None:
            continue
        cc = _liters_to_cc(liters)
        if cc is None:
            continue
        label = f"{liters:g} L" if liters < 30 else f"{cc} cc"
        return cc, label
    return None, None


def extract_horsepower(listing: dict) -> Optional[float]:
    """Best-effort HP from Autotrader inventory fields / free text."""
    candidates: List[Any] = [
        listing.get("horsepower"),
        listing.get("horsePower"),
        listing.get("maxHorsepower"),
        listing.get("engineHorsepower"),
        listing.get("engineHP"),
        listing.get("totalHorsepower"),
        listing.get("hp"),
        listing.get("power"),
        listing.get("outputHorsepower"),
    ]
    eng = listing.get("engine")
    if isinstance(eng, dict):
        candidates.extend(
            [
                eng.get("horsepower"),
                eng.get("horsePower"),
                eng.get("maxHorsepower"),
                eng.get("hp"),
                eng.get("power"),
                eng.get("name"),
                eng.get("description"),
            ]
        )
    specs = listing.get("specifications") if isinstance(listing.get("specifications"), dict) else {}
    for key in ("horsepower", "engineHorsepower", "engineDescription", "power", "engine"):
        node = specs.get(key)
        if isinstance(node, dict):
            candidates.append(node.get("value") or node.get("label"))
        elif node not in (None, ""):
            candidates.append(node)

    # Free-text fallback in title / engine description / features (rare but useful).
    for extra in (
        listing.get("listingTitle"),
        listing.get("listingTitleLong"),
        listing.get("engineDescription"),
        *(flatten_features(listing)[:40]),
    ):
        if extra:
            candidates.append(extra)

    for raw in candidates:
        if raw is None or raw == "":
            continue
        if isinstance(raw, (int, float)):
            v = float(raw)
            if 20 <= v <= 2000:
                return v
            continue
        s = str(raw).strip()
        m = _HP_RE.search(s)
        if m:
            try:
                v = float(m.group("hp"))
                if 20 <= v <= 2000:
                    return v
            except ValueError:
                pass
        # bare number only if field name strongly suggests HP (already filtered above)
        digits = "".join(ch for ch in s if ch.isdigit() or ch == ".")
        if digits and s.replace(" ", "").lower() in (digits, digits + "hp", digits + "ps"):
            try:
                v = float(digits)
                if 20 <= v <= 2000:
                    return v
            except ValueError:
                pass
    return None


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
    if not fuel_name:
        fuel_name, _ = _name_code(listing.get("fuelTypeName") or listing.get("fuelTypeGroup"))
    if not fuel_name:
        fuel_name, _ = _name_code(listing.get("engineType"))
    eng_node = listing.get("engine") if isinstance(listing.get("engine"), dict) else {}
    if not fuel_name:
        # engine.name в AT — тип силовой установки ("Hybrid", "Gasoline", "Electric").
        fuel_name, _ = _name_code(eng_node.get("name") or eng_node.get("fuelType"))
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
    disp_cc, disp_label = extract_displacement_cc(listing)
    power_hp = extract_horsepower(listing)

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
        "displacement_cc": disp_cc,
        "displacement": disp_label or disp_cc,
        "engine_volume": disp_cc,
        "power_hp": power_hp,
        "power": str(int(power_hp)) if power_hp is not None else None,
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
    # Мощность уже на ingest: слой нашей HP-библиотеки (data/us_engine_map.json, офлайн).
    # vPIC по VIN — только при USA_VIN_POWER_AT_INGEST=1; иначе добьёт catalog sync.
    # Best-effort: библиотека/сеть не должны ломать парсинг.
    try:
        import us_power

        us_power.enrich_usa_power_at_ingest(car)
    except Exception as e:  # pragma: no cover - защита от отсутствия backend в sys.path
        log.debug("autotrader: USA power enrich skipped: %s", e)

    # drop Nones in top-level optional clutter (keep explicit falsy ints)
    return car


def normalize_listing_async_ready(listing: dict, **kwargs: Any) -> Dict[str, Any]:
    """Sync helper name aligned with che168 *_async pattern callers."""
    return normalize_listing(listing, **kwargs)
