"""Нормализация ответов Che168 Global → payload каталога (CPU-bound через executor)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from functools import partial
from typing import Any, Dict, List, Optional

from scraper_pipeline.che168.api_outcome import che168_extract_similar_ids, che168_flatten_dealer
from clean_layers import build_catalog_clean_layers
from raw_json_contract import validate_raw_json_min_contract
from scraper_pipeline.che168.listing_cluster import (
    che168_recommend_raw_items,
    cluster_che168_similar_listings,
    resolve_cluster_calibration,
)

log = logging.getLogger(__name__)

RAW_ENVELOPE_VERSION = "che168.raw.v1"
PARSER_SCHEMA_VERSION = "che168.normalized.v1"


def _shape_hash(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    keys = sorted(str(k) for k in payload.keys())
    if not keys:
        return ""
    return hashlib.sha1("|".join(keys).encode("utf-8")).hexdigest()[:12]


def _unwrap_layer(d: Any) -> dict:
    if not isinstance(d, dict):
        return {}
    for k in ("result", "data", "carinfo"):
        v = d.get(k)
        if isinstance(v, dict) and len(v) >= 3:
            return v
    return d


def che168_listing_numeric_id(item: dict) -> str:
    for k in ("id", "infoid", "infoId", "InfoId", "carid", "CarId"):
        v = item.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _collect_image_urls_from_dict(carinfo: dict, *, prepend_cover: bool) -> List[str]:
    chunk: List[str] = []
    seen_local: set[str] = set()
    for key in ("images", "photo_list", "picurls", "picUrls", "photos", "photolist", "imageList", "imglist"):
        raw = carinfo.get(key)
        if isinstance(raw, str) and raw.strip():
            raw = [raw]
        if not isinstance(raw, list):
            continue
        for x in raw:
            if isinstance(x, str) and x.strip():
                u = x.strip()
                if u not in seen_local:
                    seen_local.add(u)
                    chunk.append(u)
            elif isinstance(x, dict):
                u = (
                    x.get("url")
                    or x.get("Url")
                    or x.get("picurl")
                    or x.get("picUrl")
                    or x.get("imageurl")
                    or x.get("imgUrl")
                )
                if isinstance(u, str) and u.strip():
                    u = u.strip()
                    if u not in seen_local:
                        seen_local.add(u)
                        chunk.append(u)
    cover = (
        carinfo.get("cover_image")
        or carinfo.get("picurl")
        or carinfo.get("picUrl")
        or carinfo.get("imageurl")
        or carinfo.get("imgurl")
        or carinfo.get("photo")
    )
    if isinstance(cover, str) and cover.strip():
        u = cover.strip()
        if u not in seen_local:
            seen_local.add(u)
            if prepend_cover:
                chunk.insert(0, u)
            else:
                chunk.append(u)
    return chunk


def _collect_image_urls(carinfo: dict, list_item: Optional[dict] = None) -> List[str]:
    """Сначала carinfo, затем URL из листинга."""
    out: List[str] = []
    seen: set[str] = set()
    for i, src in enumerate([x for x in (carinfo, list_item) if isinstance(x, dict) and x]):
        chunk = _collect_image_urls_from_dict(src, prepend_cover=(i == 0))
        for u in chunk:
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def _first_non_empty_str(*sources: Any, keys: tuple[str, ...]) -> Optional[str]:
    for src in sources:
        if not isinstance(src, dict):
            continue
        for k in keys:
            v = src.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
    return None


def _extract_geo(
    carinfo: dict,
    list_item: dict,
    cookie_hints: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    city = _first_non_empty_str(
        carinfo,
        list_item,
        keys=(
            "cityname",
            "cityName",
            "city",
            "City",
            "locationcity",
            "locationCity",
            "areaname",
            "areaName",
            "districtname",
            "districtName",
        ),
    )
    province = _first_non_empty_str(
        carinfo,
        list_item,
        keys=("provincename", "provinceName", "province", "state", "statename"),
    )
    region = _first_non_empty_str(
        carinfo,
        list_item,
        keys=("regionname", "region", "countryname", "countryName"),
    )
    area_id = _first_non_empty_str(
        carinfo,
        list_item,
        keys=("areaid", "areaId", "cityid", "cityId", "cid", "locationid", "locationId"),
    )
    address = _first_non_empty_str(
        carinfo,
        list_item,
        keys=("address", "addressDetail", "shopaddress", "dealeraddress", "fulladdress"),
    )
    out: Dict[str, Any] = {}
    if city:
        out["che168_city"] = city
    if province:
        out["che168_province"] = province
    if region:
        out["che168_region"] = region
    if area_id:
        out["che168_area_id"] = area_id
    if address:
        out["che168_address_line"] = address
    if cookie_hints:
        if cookie_hints.get("area"):
            out["che168_cookie_area"] = str(cookie_hints["area"]).strip()
        if cookie_hints.get("is_overseas") is not None:
            out["che168_cookie_is_overseas"] = str(cookie_hints.get("is_overseas")).strip()
    return out


def _parse_api_datetime_to_iso(val: Any) -> Optional[str]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        n = int(val)
        if n > 10_000_000_000:
            n //= 1000
        if 946684800 <= n <= 4102444800:
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(n))
        return None
    s = str(val).strip()
    if not s:
        return None
    s_iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        dt = datetime.fromisoformat(s_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(s[:10], fmt)
            return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return None


def _extract_datetimes(carinfo: dict, list_item: dict) -> Dict[str, str]:
    out: Dict[str, str] = {}
    first_reg = _first_non_empty_str(
        carinfo,
        list_item,
        keys=(
            "firstregdate",
            "firstRegDate",
            "firstregistdate",
            "registeddate",
            "registerdate",
            "registrationdate",
            "licenseddate",
            "licensedDate",
            "regdate",
            "RegDate",
        ),
    )
    pub = _first_non_empty_str(
        carinfo,
        list_item,
        keys=(
            "publishdate",
            "publishDate",
            "pubdate",
            "pubDate",
            "createtime",
            "createTime",
            "createdate",
            "createDate",
            "listdate",
            "publicdate",
            "publish_time",
            "publishedat",
        ),
    )
    price_upd = _first_non_empty_str(
        carinfo,
        list_item,
        keys=(
            "pricedate",
            "priceDate",
            "pricemodifytime",
            "priceModifyTime",
            "pricetime",
            "lastpriceupdatetime",
            "lastPriceUpdateTime",
        ),
    )
    modified = _first_non_empty_str(
        carinfo,
        list_item,
        keys=(
            "updatetime",
            "updateTime",
            "modifiedtime",
            "modifiedTime",
            "lastmodifytime",
            "lastModifyTime",
            "editdate",
        ),
    )
    mapping = (
        ("che168_first_registration_at", first_reg),
        ("che168_listing_published_at", pub),
        ("che168_price_updated_at", price_upd),
        ("che168_listing_modified_at", modified),
    )
    for key, raw in mapping:
        iso = _parse_api_datetime_to_iso(raw) if raw else None
        if iso:
            out[key] = iso
    return out


def _extract_description(carinfo: dict, list_item: dict) -> Optional[str]:
    raw = _first_non_empty_str(
        carinfo,
        list_item,
        keys=(
            "description",
            "Description",
            "remark",
            "content",
            "cardesc",
            "carDesc",
            "intro",
            "summary",
            "dealerdesc",
            "dealerDesc",
            "memo",
            "details",
            "cardescription",
            "carDescription",
            "subtitle",
            "subTitle",
        ),
    )
    return raw if raw and len(raw) > 1 else None


def _flatten_specconfig_enriched(specconfig: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            name = node.get("name") or node.get("itemname") or node.get("title") or node.get("configName")
            sub = node.get("list") or node.get("items") or node.get("sublist") or node.get("valueitems")
            price_v = node.get("price")
            has_price = price_v is not None and str(price_v).strip() != ""
            if name and str(name).strip() and (not isinstance(sub, list) or has_price):
                row: Dict[str, Any] = {"name": str(name).strip()}
                if has_price:
                    row["price"] = price_v
                val = node.get("value") or node.get("dispvalue") or node.get("subvalue")
                if val is not None and str(val).strip() != "":
                    row["value"] = val
                if len(row) > 1:
                    out.append(row)
            if isinstance(sub, list):
                for x in sub:
                    walk(x)
            elif isinstance(sub, dict):
                walk(sub)
            else:
                for v in node.values():
                    if isinstance(v, (list, dict)) and v is not sub:
                        walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(specconfig)
    return out


def _dedupe_ids_preserve_order(ids: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in ids:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _taxonomy_apply(
    mark: Optional[str],
    model: Optional[str],
    taxonomy: Optional[Dict[str, Any]],
) -> tuple[Optional[str], Optional[str], Dict[str, Any]]:
    meta: Dict[str, Any] = {}
    if not taxonomy:
        return mark, model, meta
    ma = taxonomy.get("mark_aliases") if isinstance(taxonomy.get("mark_aliases"), dict) else {}
    mo = taxonomy.get("model_aliases") if isinstance(taxonomy.get("model_aliases"), dict) else {}

    def _alias_map(d: dict) -> Dict[str, str]:
        return {str(k).strip().lower(): str(v).strip() for k, v in d.items() if k and v}

    ma_l = _alias_map(ma)
    mo_l = _alias_map(mo)
    m_can, mo_can = mark, model
    if mark and mark.strip().lower() in ma_l:
        m_can = ma_l[mark.strip().lower()]
        meta["mark_canonical_source"] = "alias"
    if model and model.strip().lower() in mo_l:
        mo_can = mo_l[model.strip().lower()]
        meta["model_canonical_source"] = "alias"
    return m_can, mo_can, meta


def _resolve_mark_model_canonical(
    mark: Optional[str],
    model: Optional[str],
    taxonomy: Optional[Dict[str, Any]],
    ci: dict,
    li: dict,
) -> tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """Имя бренда из /brand (brand_by_id), затем YAML-алиасы."""
    meta: Dict[str, Any] = {}
    mark_c, model_c = mark, model
    bid: Optional[int] = None
    for src in (li, ci):
        if not isinstance(src, dict):
            continue
        for k in ("brandid", "brandId", "brand_id"):
            v = src.get(k)
            if v is None or str(v).strip() == "":
                continue
            s = str(v).strip()
            if s.isdigit():
                bid = int(s)
                break
        if bid is not None:
            break
    if bid is not None and taxonomy:
        bmap = taxonomy.get("brand_by_id")
        if isinstance(bmap, dict):
            api_mark = bmap.get(str(bid))
            if api_mark and str(api_mark).strip():
                mark_c = str(api_mark).strip()
                meta["mark_canonical_source"] = "brand_api_id"
                meta["che168_brand_id"] = bid
    mark_c, model_c, am = _taxonomy_apply(mark_c, model_c, taxonomy)
    meta.update(am)

    sid: Optional[int] = None
    for src in (li, ci):
        if not isinstance(src, dict):
            continue
        for k in ("seriesid", "seriesId", "serieid", "series_id"):
            v = src.get(k)
            if v is None or str(v).strip() == "":
                continue
            s = str(v).strip()
            if s.isdigit():
                sid = int(s)
                break
            try:
                sid = int(float(s))
                if sid > 0:
                    break
            except (TypeError, ValueError):
                continue
        if sid is not None:
            break
    if sid is not None and taxonomy:
        smap = taxonomy.get("seriesid_to_model_name")
        if isinstance(smap, dict):
            api_model = smap.get(str(sid))
            if api_model and str(api_model).strip():
                model_c = str(api_model).strip()
                meta["model_canonical_source"] = "series_api_id"
                meta["che168_series_id"] = sid

    return mark_c, model_c, meta


def _parser_shape_fingerprints(list_item: dict, ci: dict) -> Dict[str, str]:
    def _h(keys: List[str]) -> str:
        if not keys:
            return ""
        return hashlib.sha1("|".join(keys).encode("utf-8")).hexdigest()[:16]

    li_k = sorted(str(k) for k in list_item.keys())
    ci_k = sorted(str(k) for k in ci.keys())
    return {
        "list_item_keys_sha1": _h(li_k),
        "carinfo_keys_sha1": _h(ci_k),
        "list_item_key_count": str(len(li_k)),
        "carinfo_key_count": str(len(ci_k)),
    }


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            s = v.strip().replace("\u00a0", " ").replace(" ", "").replace(",", "").split(".")[0]
            if not s:
                return None
            return int(float(s))
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(str(v).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def normalize_price_cny_detailed(
    raw: Any, *, assume_wan_yuan: bool
) -> tuple[Optional[float], Dict[str, Any]]:
    """
    Возвращает (цена в CNY, метаданные интерпретации для аудита и Meili).
    rule: config_assume_wan_yuan | heuristic_small_decimal_wan | heuristic_small_integer_wan | raw_cny_integer | none
    """
    meta: Dict[str, Any] = {"che168_price_raw_input": raw, "che168_price_cny_rule": "none"}
    v = _safe_float(raw)
    if v is None or v <= 0:
        return None, meta
    if assume_wan_yuan:
        meta["che168_price_cny_rule"] = "config_assume_wan_yuan"
        return round(v * 10_000.0, 2), meta
    if v < 1000 and abs(v - int(v)) > 1e-6:
        meta["che168_price_cny_rule"] = "heuristic_small_decimal_wan"
        return round(v * 10_000.0, 2), meta
    if v < 500:
        meta["che168_price_cny_rule"] = "heuristic_small_integer_wan"
        return round(v * 10_000.0, 2), meta
    meta["che168_price_cny_rule"] = "raw_cny_integer"
    return round(v, 2), meta


def normalize_price_cny(raw: Any, *, assume_wan_yuan: bool) -> Optional[float]:
    p, _ = normalize_price_cny_detailed(raw, assume_wan_yuan=assume_wan_yuan)
    return p


def _vin_from(carinfo: dict) -> Optional[str]:
    for k in ("vin", "VIN", "vehicleIdentificationNumber", "frameno", "frameNo"):
        s = carinfo.get(k)
        if s is not None and str(s).strip():
            return str(s).strip().upper()
    return None


def _vin_from_sources(carinfo: dict, list_item: dict) -> Optional[str]:
    for src in (carinfo, list_item):
        if isinstance(src, dict) and src:
            v = _vin_from(src)
            if v:
                return v
    return None


def _mileage_km(carinfo: dict, list_item: dict) -> Optional[int]:
    for src in (carinfo, list_item):
        for k in ("mileage", "mileagekm", "mileageKm", "totalmileage"):
            n = _safe_int(src.get(k))
            if n is not None and n >= 0:
                return n
    return None


def _year_from(carinfo: dict, list_item: dict) -> Optional[int]:
    for src in (carinfo, list_item):
        y = _safe_int(src.get("year"))
        if y and 1980 <= y <= 2035:
            return y
    return None


def _brand_model_title(carinfo: dict, list_item: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    title = carinfo.get("title") or list_item.get("title")
    title = str(title).strip() if title else None
    mark = (
        carinfo.get("brandname")
        or carinfo.get("brandName")
        or carinfo.get("BrandName")
        or list_item.get("brandname")
        or list_item.get("brandName")
    )
    mark = str(mark).strip() if mark else None
    model = (
        carinfo.get("seriesname")
        or carinfo.get("seriesName")
        or carinfo.get("vehicleName")
        or carinfo.get("modelname")
        or carinfo.get("modelName")
        or list_item.get("seriesname")
        or list_item.get("modelname")
    )
    model = str(model).strip() if model else None
    return mark, model, title


def _flatten_specconfig_options(specconfig: Any) -> List[str]:
    if specconfig is None:
        return []
    opts: List[str] = []
    if isinstance(specconfig, dict):
        for k in ("list", "configlist", "items", "optionlist", "data", "result"):
            v = specconfig.get(k)
            if isinstance(v, list):
                return _flatten_specconfig_options(v)
        for v in specconfig.values():
            opts.extend(_flatten_specconfig_options(v))
        return opts
    if isinstance(specconfig, list):
        for x in specconfig:
            if isinstance(x, str) and x.strip():
                opts.append(x.strip())
            elif isinstance(x, dict):
                name = x.get("name") or x.get("itemname") or x.get("title") or x.get("configName")
                if name:
                    opts.append(str(name).strip())
                sub = x.get("list") or x.get("items")
                if sub:
                    opts.extend(_flatten_specconfig_options(sub))
        return opts
    return opts


def _power_hp_from_hints(spec_hints: Dict[str, Any]) -> Optional[int]:
    p = spec_hints.get("power")
    if p is None:
        return None
    s = str(p).strip()
    m = re.search(r"(\d{2,4})\s*(?:hp|ps|к\.?с\.?|马力)?", s, re.I)
    if m:
        try:
            v = int(m.group(1))
            return v if 40 <= v <= 2000 else None
        except ValueError:
            return None
    return _safe_int(s)


def _displacement_cc_from_spec(spec_raw: dict) -> Optional[int]:
    for k in ("displacementml", "displacementMl", "displacement", "liter"):
        v = spec_raw.get(k)
        if v is None:
            continue
        n = _safe_int(v)
        if n is not None and 500 <= n <= 12000:
            return n
        f = _safe_float(v)
        if f is not None and 0.5 <= f <= 8.0:
            cc = int(round(f * 1000))
            if 500 <= cc <= 12000:
                return cc
    return None


def _spec_fields(specparam: Any) -> Dict[str, Any]:
    body = specparam
    if isinstance(specparam, dict):
        body = _unwrap_layer(specparam)
    if not isinstance(body, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, targets in (
        ("displacement", ("displacement", "displacementml", "liter")),
        ("gearbox", ("gearbox", "transmission", "transmissiontype")),
        ("fueltype", ("fueltype", "fuelType", "engine")),
        ("drivemode", ("drivemode", "driveType", "drive")),
        ("bodytype", ("bodytype", "bodyType", "level")),
        ("color", ("color", "bodycolor")),
        ("power", ("power", "horsepower", "maxpower")),
    ):
        for t in targets:
            v = body.get(t)
            if v is not None and str(v).strip():
                out[key] = v
                break
    return out


def _build_raw_envelope(
    *,
    list_item: Optional[Dict[str, Any]],
    carinfo: Optional[Dict[str, Any]],
    specparam: Optional[Dict[str, Any]],
    specconfig: Optional[Dict[str, Any]],
    recommend: Optional[Dict[str, Any]],
    report_summary: Optional[Dict[str, Any]],
    source_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    sources: Dict[str, Any] = {
        "list_item": list_item if isinstance(list_item, dict) else None,
        "carinfo": carinfo if isinstance(carinfo, dict) else None,
        "specparam": specparam if isinstance(specparam, dict) else None,
        "specconfig": specconfig if isinstance(specconfig, dict) else None,
        "recommend": recommend if isinstance(recommend, dict) else None,
        "report_summary": report_summary if isinstance(report_summary, dict) else None,
    }
    expected = list(sources.keys())
    present = [k for k, v in sources.items() if isinstance(v, dict)]
    missing = [k for k in expected if k not in present]
    return {
        "raw_schema_version": RAW_ENVELOPE_VERSION,
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": sources,
        "integrity": {
            "expected_sources": expected,
            "present_sources": present,
            "missing_sources": missing,
            "coverage_pct": round((len(present) / len(expected)) * 100.0, 2) if expected else 0.0,
            "shape_hashes": {k: _shape_hash(v) for k, v in sources.items()},
        },
        "source_meta": source_meta or {},
    }


def parse_one_che168_car_sync(
    *,
    external_id: str,
    list_item: dict,
    carinfo: Optional[dict],
    specparam: Optional[dict],
    specconfig: Optional[dict],
    recommend: Optional[dict],
    report_summary: Optional[dict],
    assume_price_wan_yuan: bool = False,
    source_meta: Optional[Dict[str, Dict[str, Any]]] = None,
    taxonomy: Optional[Dict[str, Any]] = None,
    session_cookie_hints: Optional[Dict[str, str]] = None,
    listing_cluster: Optional[Dict[str, Any]] = None,
) -> Optional[dict]:
    if not external_id:
        return None
    car_id = f"che168-{external_id}"
    li = list_item if isinstance(list_item, dict) else {}
    ci = _unwrap_layer(carinfo) if isinstance(carinfo, dict) else {}
    if not ci and not li:
        return None

    mark, model, title = _brand_model_title(ci, li)
    mark_c, model_c, tax_meta = _resolve_mark_model_canonical(mark, model, taxonomy, ci, li)
    raw_price = ci.get("price") if ci.get("price") not in (None, "") else li.get("price")
    price_cny, price_meta = normalize_price_cny_detailed(raw_price, assume_wan_yuan=assume_price_wan_yuan)

    spec_raw = _unwrap_layer(specparam) if isinstance(specparam, dict) else {}
    spec_hints = _spec_fields(spec_raw)
    opts = _flatten_specconfig_options(specconfig)
    opts_enriched = _flatten_specconfig_enriched(specconfig)

    displacement_label = None
    if spec_hints.get("displacement"):
        displacement_label = str(spec_hints["displacement"]).strip() or None

    dealer_flat = che168_flatten_dealer(report_summary) if report_summary else {}
    similar_raw = che168_extract_similar_ids(recommend, limit=40) if recommend else []
    similar_dedup = _dedupe_ids_preserve_order(similar_raw)
    similar_dedup = [x for x in similar_dedup if x != str(external_id)]
    disp_cc = _displacement_cc_from_spec(spec_raw) if spec_raw else None
    p_hp = _power_hp_from_hints(spec_hints)

    geo = _extract_geo(ci, li, session_cookie_hints)
    dt_fields = _extract_datetimes(ci, li)
    description = _extract_description(ci, li)
    images = _collect_image_urls(ci if ci else {}, li if li else None)
    vin = _vin_from_sources(ci, li)
    yr = _year_from(ci, li)
    km_v = _mileage_km(ci, li)
    trim = (
        ci.get("trimname")
        or ci.get("trimName")
        or ci.get("carname")
        or ci.get("specname")
        or li.get("subtitle")
    )

    data: Dict[str, Any] = {
        "id": car_id,
        "source": "che168",
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "che168_listing_id": external_id,
        "inner_id": external_id,
        "mark": mark,
        "model": model,
        "title": title,
        "year": yr,
        "km_age": km_v,
        "price_cny": price_cny,
        "price_on_request": bool(price_cny is None or price_cny <= 0),
        "che168_price_raw": raw_price,
        "images": images,
        "vin": vin,
        "configuration": trim,
        "color": spec_hints.get("color") or ci.get("color") or li.get("color"),
        "body_type": spec_hints.get("bodytype"),
        "engine_type": spec_hints.get("fueltype"),
        "transmission_type": spec_hints.get("gearbox"),
        "drive_type": spec_hints.get("drivemode"),
        "power_hp": p_hp,
        "displacement_cc": disp_cc,
        "che168_params_raw": spec_raw if spec_raw else None,
        "che168_recommended_options": opts or None,
        "che168_options_enriched": opts_enriched if opts_enriched else None,
        "che168_displacement_label": displacement_label,
        "che168_dealer": dealer_flat if dealer_flat else None,
        "che168_similar_listing_ids": similar_dedup if similar_dedup else None,
        "che168_similar_raw_count": len(similar_raw) if similar_raw else 0,
        "description": description,
        "listing_text": description,
    }
    if mark_c and mark_c != mark:
        data["mark_canonical"] = mark_c
    if model_c and model_c != model:
        data["model_canonical"] = model_c
    if tax_meta:
        data["che168_taxonomy_meta"] = tax_meta
    data.update(price_meta)
    data.update(geo)
    data.update(dt_fields)
    if similar_raw and len(similar_dedup) < len(similar_raw):
        data["che168_similar_duplicates_removed"] = len(similar_raw) - len(similar_dedup)

    lc = listing_cluster if isinstance(listing_cluster, dict) else {}
    if lc.get("enabled", True) is not False and recommend:
        cal = resolve_cluster_calibration(lc)
        rec_items = che168_recommend_raw_items(recommend, limit=int(lc.get("recommend_limit", 40) or 40))
        tel: Optional[Dict[str, int]] = {} if lc.get("telemetry_near_miss", True) is not False else None
        cl = cluster_che168_similar_listings(
            str(external_id),
            vin=vin,
            mark=mark,
            model=model,
            year=yr,
            price_cny=price_cny,
            km=km_v,
            recommend_items=rec_items,
            price_rel_tol=cal["price_rel_tol"],
            km_abs_tol=cal["km_abs_tol"],
            year_max_diff=cal["year_max_diff"],
            near_miss_price_rel_cap=cal["near_miss_price_rel_cap"],
            near_miss_km_abs_cap=cal["near_miss_km_abs_cap"],
            telemetry=tel,
        )
        if tel:
            data["che168_cluster_telemetry"] = {k: v for k, v in tel.items() if v}
        if cl.get("cluster_id"):
            data["che168_listing_cluster_id"] = cl["cluster_id"]
            data["che168_listing_cluster_peer_ids"] = cl["peer_ids"] or None
            data["che168_listing_cluster_method"] = cl["method"]
            data["che168_listing_cluster_size"] = cl["cluster_size"]

    for k in list(data.keys()):
        if data[k] is None:
            data.pop(k)

    envelope = _build_raw_envelope(
        list_item=li,
        carinfo=carinfo if isinstance(carinfo, dict) else None,
        specparam=specparam if isinstance(specparam, dict) else None,
        specconfig=specconfig if isinstance(specconfig, dict) else None,
        recommend=recommend if isinstance(recommend, dict) else None,
        report_summary=report_summary if isinstance(report_summary, dict) else None,
        source_meta=source_meta,
    )
    data["raw_envelope"] = envelope

    missing_required: List[str] = []
    if not mark:
        missing_required.append("mark")
    if price_cny is None or price_cny <= 0:
        missing_required.append("price_cny")

    n_img = len(images)
    n_spec_keys = len(spec_raw) if spec_raw else 0
    n_opt = len(opts) if opts else 0
    completeness = {
        "has_vin": bool(vin),
        "image_count": n_img,
        "has_mileage": km_v is not None,
        "has_trim": bool(trim and str(trim).strip()),
        "has_geo_city": bool(geo.get("che168_city")),
        "has_description": bool(description),
        "spec_param_fields": n_spec_keys,
        "options_flat_count": n_opt,
        "options_enriched_count": len(opts_enriched) if opts_enriched else 0,
    }
    score = 100
    score -= 12 if not completeness["has_vin"] else 0
    score -= min(20, (3 if n_img == 0 else 0) + max(0, 5 - n_img) * 2)
    score -= 6 if not completeness["has_mileage"] else 0
    score -= 5 if not completeness["has_trim"] else 0
    score -= 4 if not completeness["has_description"] else 0
    score -= 3 if not completeness["has_geo_city"] else 0
    score -= min(10, max(0, 8 - min(n_spec_keys, 8)))
    score -= len(missing_required) * 10
    score = max(0, min(100, score))

    quality = {
        "missing_required_fields": missing_required,
        "raw_coverage_pct": float(envelope["integrity"]["coverage_pct"]),
        "raw_quality_score": score,
        "completeness": completeness,
        "price_interpretation_rule": price_meta.get("che168_price_cny_rule"),
    }
    if envelope["integrity"]["missing_sources"]:
        quality.setdefault("reasons", []).append("raw_sources_missing")
    if dealer_flat.get("dealer_name"):
        data["seller"] = dealer_flat["dealer_name"]
    data["data_quality"] = quality

    data.update(build_catalog_clean_layers(data))
    contract_violations = validate_raw_json_min_contract(data)
    data["data_quality"]["contract_violations"] = contract_violations
    if contract_violations:
        data["data_quality"].setdefault("reasons", []).append("raw_json_min_contract_violation")
    try:
        data["parser_source_shapes"] = {
            "list_item": sorted(str(k) for k in li.keys()),
            "carinfo": sorted(str(k) for k in (ci or {}).keys()),
        }
        data["parser_shape_fingerprints"] = _parser_shape_fingerprints(li, ci)
    except Exception:
        pass

    pub_iso = dt_fields.get("che168_listing_published_at")
    if pub_iso:
        data.setdefault("created_at", pub_iso)
        data.setdefault("listing_published_at", pub_iso)

    out = {"id": car_id, "data": data, "_raw": envelope}
    return out


async def parse_one_che168_car_async(
    *,
    external_id: str,
    list_item: dict,
    carinfo: Optional[dict],
    specparam: Optional[dict],
    specconfig: Optional[dict],
    recommend: Optional[dict],
    report_summary: Optional[dict],
    assume_price_wan_yuan: bool = False,
    source_meta: Optional[Dict[str, Dict[str, Any]]] = None,
    taxonomy: Optional[Dict[str, Any]] = None,
    session_cookie_hints: Optional[Dict[str, str]] = None,
    listing_cluster: Optional[Dict[str, Any]] = None,
) -> Optional[dict]:
    loop = asyncio.get_running_loop()
    fn = partial(
        parse_one_che168_car_sync,
        external_id=external_id,
        list_item=list_item,
        carinfo=carinfo,
        specparam=specparam,
        specconfig=specconfig,
        recommend=recommend,
        report_summary=report_summary,
        assume_price_wan_yuan=assume_price_wan_yuan,
        source_meta=source_meta,
        taxonomy=taxonomy,
        session_cookie_hints=session_cookie_hints,
        listing_cluster=listing_cluster,
    )
    return await loop.run_in_executor(None, fn)
