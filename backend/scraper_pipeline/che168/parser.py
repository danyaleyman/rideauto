"""Нормализация ответов Che168 Global → payload каталога (CPU-bound через executor)."""

from __future__ import annotations

import asyncio
import hashlib
import json
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

# Соседние к `result`/`data` поля в сыром JSON /carinfo (иначе `_unwrap_layer` их отбрасывает).
_CHE168_CARINFO_ENVELOPE_MEDIA_KEYS: tuple[str, ...] = (
    "images",
    "photo_list",
    "picurls",
    "picUrls",
    "photos",
    "photolist",
    "imageList",
    "imglist",
    "gallery",
    "album",
    "carImages",
    "carimages",
    "cover_image",
    "picurl",
    "picUrl",
    "imageurl",
    "imgurl",
    "photo",
    "specid",
    "specId",
    "dealerid",
    "dealerId",
    "paramkey",
    "paramKey",
)

_CHE168_OPTIONAL_MEDIA_BUCKETS: tuple[str, ...] = (
    "extinfo",
    "extendinfo",
    "extra",
    "ext",
    "appendix",
    "other",
    "spec",
    "params",
)

_URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>|]+", re.I)


def _is_likely_che168_vehicle_photo_url(u: str) -> bool:
    """Отсекаем соцссылки дилера; оставляем типичные CDN Авто-дома/Che168 global."""
    low = u.lower()
    if any(x in low for x in ("wa.me", "weixin.qq", "work.weixin", "mailto:", "tel:", "javascript:")):
        return False
    return (
        "erscglobal" in low
        or "/escimg/" in low
        or "autoimg.cn" in low
        or "autohomecar" in low
        or "che168.com" in low
    )


def _deep_collect_car_photo_urls(obj: Any, *, max_urls: int = 48, max_depth: int = 22) -> List[str]:
    """Рекурсивно собирает URL фото из произвольного вложения ответа API (нестандартные ключи)."""
    seen: set[str] = set()
    out: List[str] = []

    def visit(x: Any, depth: int) -> None:
        if len(out) >= max_urls or depth > max_depth:
            return
        if isinstance(x, str):
            s = x.strip()
            if s.startswith("http") and _is_likely_che168_vehicle_photo_url(s) and s not in seen:
                seen.add(s)
                out.append(s)
            return
        if isinstance(x, dict):
            for v in x.values():
                visit(v, depth + 1)
            return
        if isinstance(x, list):
            for v in x:
                visit(v, depth + 1)

    visit(obj, 0)
    return out


# Галерея на сайте подгружается с CDN; URL часто вшиты в HTML/SSR до гидрации (см. Network → Img).
_CHE168_DETAIL_GALLERY_RE = re.compile(
    r"https://erscglobal\d*\.autoimg\.cn/escimg/[^\s\"'<>)]+",
    re.IGNORECASE,
)


def extract_gallery_urls_from_detail_html(html: str, *, max_urls: int = 96) -> List[str]:
    """Достаёт URL фото из HTML страницы объявления global.che168.com (и встроенного JSON)."""
    if not html or len(html) < 80:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for m in _CHE168_DETAIL_GALLERY_RE.finditer(html):
        u = m.group(0).rstrip("\\,.);'\"")
        if not _is_likely_che168_vehicle_photo_url(u):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= max_urls:
            break
    return out


def merge_che168_image_url_lists(primary: List[str], secondary: List[str]) -> List[str]:
    """Порядок: сначала primary (страница детали — обычно полный набор и 1400x0), затем доп. из API."""
    seen: set[str] = set()
    merged: List[str] = []
    for u in primary:
        if u and u not in seen:
            seen.add(u)
            merged.append(u)
    for u in secondary:
        if u and u not in seen:
            seen.add(u)
            merged.append(u)
    return merged


def che168_collect_api_layer_photo_urls(ci_body: dict) -> List[str]:
    """Все URL фото, уже видимые в слое после merge API /carinfo (без HTML)."""
    if not isinstance(ci_body, dict):
        return []
    return _deep_collect_car_photo_urls(ci_body, max_urls=96)


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


def _is_empty_media_value(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def merge_che168_api_carinfo_envelope(raw: dict) -> dict:
    """
    Собирает слой карточки для парсера: внутренний объект из `_unwrap_layer(raw)`
    плюс медиа/обложки с верхнего уровня ответа API (и типичных вложенных bucket-ов),
    которые иначе теряются при `carinfo = result`.
    """
    inner = _unwrap_layer(raw)
    out: Dict[str, Any] = dict(inner) if isinstance(inner, dict) else {}

    def _overlay(src: Any) -> None:
        if not isinstance(src, dict):
            return
        for k in _CHE168_CARINFO_ENVELOPE_MEDIA_KEYS:
            v = src.get(k)
            if _is_empty_media_value(v):
                continue
            if k not in out or _is_empty_media_value(out.get(k)):
                out[k] = v

    _overlay(raw)
    for bk in _CHE168_OPTIONAL_MEDIA_BUCKETS:
        b = raw.get(bk)
        if isinstance(b, dict):
            _overlay(b)

    cur_im = out.get("images")
    cur_n = 0
    if isinstance(cur_im, list):
        cur_n = len(cur_im)
    elif isinstance(cur_im, str) and cur_im.strip():
        cur_n = 1
    deep = _deep_collect_car_photo_urls(raw)
    if len(deep) > cur_n:
        out["images"] = deep
    return out


def _nested_dict_candidates(payload: Any) -> List[dict]:
    out: List[dict] = []
    seen_ids: set[int] = set()

    def _add(node: Any) -> None:
        if not isinstance(node, dict):
            return
        nid = id(node)
        if nid in seen_ids:
            return
        seen_ids.add(nid)
        out.append(node)
        for k in ("result", "data", "carinfo", "detail", "vehicle", "info"):
            v = node.get(k)
            if isinstance(v, dict):
                _add(v)

    _add(payload)
    return out


def _iter_deep_nodes(payload: Any) -> List[Any]:
    out: List[Any] = []
    seen_ids: set[int] = set()

    def walk(node: Any) -> None:
        nid = id(node)
        if nid in seen_ids:
            return
        seen_ids.add(nid)
        out.append(node)
        if isinstance(node, dict):
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for x in node:
                if isinstance(x, (dict, list)):
                    walk(x)

    walk(payload)
    return out


def _norm_label_token(s: Any) -> str:
    if s is None:
        return ""
    txt = str(s).strip().lower()
    if not txt:
        return ""
    return re.sub(r"[\s\-_:/()（）\[\]【】.]+", "", txt)


def _map_spec_alias(label: Any, alias_to_key: Dict[str, str]) -> Optional[str]:
    n = _norm_label_token(label)
    if not n:
        return None
    direct = alias_to_key.get(n)
    if direct:
        return direct
    for alias, key in alias_to_key.items():
        if alias and alias in n:
            return key
    return None


def _pick_first_non_empty_with_source(sources: List[tuple[str, dict]], keys: tuple[str, ...]) -> tuple[Optional[Any], Optional[str]]:
    for src_name, src in sources:
        if not isinstance(src, dict):
            continue
        for k in keys:
            v = src.get(k)
            if v is not None and str(v).strip():
                return v, f"{src_name}.{k}"
    return None, None


def che168_listing_numeric_id(item: dict) -> str:
    for k in ("id", "infoid", "infoId", "InfoId", "carid", "CarId"):
        v = item.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _collect_image_urls_from_dict(carinfo: dict, *, prepend_cover: bool) -> List[str]:
    chunk: List[str] = []
    seen_local: set[str] = set()
    # Che168 Global /carinfo (globalapi) часто кладёт галерею в result.catepiclist[*].list.
    # После _unwrap_layer(carinfo) это становится просто carinfo["catepiclist"].
    cate = carinfo.get("catepiclist")
    if isinstance(cate, list):
        for cat in cate:
            if not isinstance(cat, dict):
                continue
            lst = cat.get("list")
            if not isinstance(lst, list):
                continue
            for x in lst:
                if isinstance(x, str) and x.strip():
                    u = x.strip()
                    if u not in seen_local:
                        seen_local.add(u)
                        chunk.append(u)
    for key in (
        "images",
        "photo_list",
        "picurls",
        "picUrls",
        "photos",
        "photolist",
        "imageList",
        "imglist",
        "gallery",
        "album",
        "carImages",
        "carimages",
    ):
        raw = carinfo.get(key)
        if isinstance(raw, str) and raw.strip():
            s = raw.strip()
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        raw = parsed
                    else:
                        raw = [s]
                except json.JSONDecodeError:
                    found = _URL_IN_TEXT.findall(s)
                    raw = found if len(found) >= 2 else [s]
            else:
                found = _URL_IN_TEXT.findall(s)
                raw = found if len(found) >= 2 else [s]
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
                    or x.get("image")
                    or x.get("image_url")
                    or x.get("big_url")
                    or x.get("bigUrl")
                    or x.get("thumb_url")
                    or x.get("thumbUrl")
                    or x.get("cover_url")
                    or x.get("coverUrl")
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
        or carinfo.get("imageUrl")
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
    all_sources: List[dict] = []
    if isinstance(carinfo, dict) and carinfo:
        all_sources.extend(_nested_dict_candidates(carinfo))
    if isinstance(list_item, dict) and list_item:
        all_sources.extend(_nested_dict_candidates(list_item))
    for i, src in enumerate(all_sources):
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
    cands: List[dict] = []
    cands.extend(_nested_dict_candidates(carinfo))
    cands.extend(_nested_dict_candidates(list_item))
    raw = _first_non_empty_str(
        *cands,
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
            "desc",
            "text",
            "detail",
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


_WAN_IN_TEXT_RE = re.compile(r"([\d.,]+)\s*万")


def normalize_price_cny_detailed(
    raw: Any, *, assume_wan_yuan: bool, price_context: str = ""
) -> tuple[Optional[float], Dict[str, Any]]:
    """
    Возвращает (цена в CNY, метаданные интерпретации для аудита и Meili).
    rule: config_assume_wan_yuan | heuristic_small_decimal_wan | heuristic_small_integer_wan | raw_cny_integer | none
    """
    meta: Dict[str, Any] = {"che168_price_raw_input": raw, "che168_price_cny_rule": "none"}
    ctx = " ".join(
        str(x).strip()
        for x in (price_context, raw if isinstance(raw, str) else "")
        if x is not None and str(x).strip()
    )
    if ctx and not assume_wan_yuan:
        mwan = _WAN_IN_TEXT_RE.search(ctx.replace("，", ","))
        if mwan:
            try:
                wan = float(mwan.group(1).replace(",", "."))
                if 0 < wan < 5000:
                    meta["che168_price_cny_rule"] = "text_embedded_wan"
                    return round(wan * 10_000.0, 2), meta
            except ValueError:
                pass
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


def normalize_price_cny(raw: Any, *, assume_wan_yuan: bool, price_context: str = "") -> Optional[float]:
    p, _ = normalize_price_cny_detailed(raw, assume_wan_yuan=assume_wan_yuan, price_context=price_context)
    return p


def _vin_from(carinfo: dict) -> Optional[str]:
    for k in ("vin", "VIN", "vehicleIdentificationNumber", "frameno", "frameNo"):
        s = carinfo.get(k)
        if s is not None and str(s).strip():
            return str(s).strip().upper()
    return None


def _vin_from_sources(carinfo: dict, list_item: dict) -> Optional[str]:
    cands: List[dict] = []
    cands.extend(_nested_dict_candidates(carinfo))
    cands.extend(_nested_dict_candidates(list_item))
    for src in cands:
        if isinstance(src, dict) and src:
            v = _vin_from(src)
            if v:
                return v
    return None


def _mileage_km(carinfo: dict, list_item: dict) -> Optional[int]:
    cands: List[dict] = []
    cands.extend(_nested_dict_candidates(carinfo))
    cands.extend(_nested_dict_candidates(list_item))
    for src in cands:
        for k in ("mileage", "mileagekm", "mileageKm", "totalmileage", "kilometer", "km", "mile"):
            n = _safe_int(src.get(k))
            if n is not None and n >= 0:
                return n
    return None


def _year_from(carinfo: dict, list_item: dict) -> Optional[int]:
    cands: List[dict] = []
    cands.extend(_nested_dict_candidates(carinfo))
    cands.extend(_nested_dict_candidates(list_item))
    for src in cands:
        for key in ("year", "modelyear", "modelYear", "regyear", "registeryear", "yearname"):
            y = _safe_int(src.get(key))
            if y and 1980 <= y <= 2035:
                return y
    return None


def _brand_model_title(carinfo: dict, list_item: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    cands: List[dict] = []
    cands.extend(_nested_dict_candidates(carinfo))
    cands.extend(_nested_dict_candidates(list_item))
    title = _first_non_empty_str(
        *cands,
        keys=("title", "carname", "carName", "name", "vehicleTitle", "subtitle", "subTitle"),
    )
    mark = _first_non_empty_str(
        *cands,
        keys=("brandname", "brandName", "BrandName", "brand", "maker", "make"),
    )
    model = _first_non_empty_str(
        *cands,
        keys=(
            "seriesname",
            "seriesName",
            "vehicleName",
            "modelname",
            "modelName",
            "model",
            "serieName",
            "trimname",
            "trimName",
        ),
    )
    return mark, model, title


def _flatten_specconfig_options(specconfig: Any) -> List[str]:
    """Рекурсивно извлекает человекочитаемые названия опций (не configid / сырые числовые id)."""
    if specconfig is None:
        return []
    out: List[str] = []
    seen: set[str] = set()

    def _push_label(s: str) -> None:
        t = s.strip()
        if not t or t.isdigit():
            return
        if t not in seen:
            seen.add(t)
            out.append(t)

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            _push_label(node)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if not isinstance(node, dict):
            return

        name = (
            node.get("name")
            or node.get("itemname")
            or node.get("title")
            or node.get("configName")
            or node.get("optionName")
            or node.get("optionname")
        )
        if isinstance(name, str) and name.strip():
            _push_label(name)
        for v in node.values():
            _walk(v)

    _walk(specconfig)
    return out


# Частые подписи опций Che168 (EN) → RU для карточки «Комплектация».
CHE168_OPTION_MAP_RU: Dict[str, str] = {
    "Adaptive M Suspension": "Адаптивная M-подвеска",
    "M Sport Brakes": "M Sport тормоза",
    "Harman Kardon sound system": "Аудиосистема Harman Kardon",
    "Head-up display": "Проекционный дисплей",
    "Wireless charging": "Беспроводная зарядка",
    "Parking Assistant Plus": "Park Assistant Plus",
    "Heated steering wheel": "Подогрев руля",
    "Lumbar support": "Поясничная поддержка",
    "Adaptive cruise control": "Адаптивный круиз-контроль",
    "Surround view camera": "Камера 360°",
    "Panoramic sunroof": "Панорамная крыша",
    "Leather upholstery": "Кожаный салон",
    "Heated seats": "Подогрев сидений",
    "Ventilated seats": "Вентиляция сидений",
    "Massage seats": "Массаж сидений",
    "Keyless entry": "Бесключевой доступ",
    "Electric tailgate": "Электропривод багажника",
    "Blind spot monitoring": "Контроль слепых зон",
    "Lane keep assist": "Удержание в полосе",
    "Traffic sign recognition": "Распознавание знаков",
}


def _map_che168_option_label_ru(label: str) -> str:
    raw = label.strip()
    if not raw:
        return raw
    if raw in CHE168_OPTION_MAP_RU:
        return CHE168_OPTION_MAP_RU[raw]
    low = raw.lower()
    for en, ru in CHE168_OPTION_MAP_RU.items():
        if en.lower() == low:
            return ru
    return raw


_CHE168_TECH_CATEGORY_SNIPPETS: tuple[str, ...] = (
    "basic specification",
    "basic parameters",
    "main specification",
    "vehicle specifications",
    "body structure",
    "body dimensions",
    "dimensions and weight",
    "dimensions & weight",
    "fuel consumption",
    "engine specification",
    "motor specification",
    "power and torque",
    "power performance",
    "emission",
    "wheel & tire",
    "wheels and tires",
    "基本参数",
    "主要参数",
    "主要规格",
    "车身尺寸",
    "车身参数",
    "发动机",
    "变速箱",
    "油耗",
    "整备质量",
    "动力",
)


def _che168_is_technical_spec_category(cat: str) -> bool:
    s = cat.strip().lower()
    if not s:
        return True
    return any(sn in s for sn in _CHE168_TECH_CATEGORY_SNIPPETS)


_CHE168_SPEC_LINE_NOISE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\d+\.\d+\s*T\b", re.I),
    re.compile(r"\b\d{2,4}\s*hp\b", re.I),
    re.compile(r"\b\d{2,4}\s*(?:hp|ps)\b", re.I),
    re.compile(r"^\d+\s*[-\s]*speed\b", re.I),
    re.compile(r"\b(?:front|rear|all)[-\s]?wheel\s+drive\b", re.I),
    re.compile(r"^\s*(?:FWD|RWD|AWD|4WD|2WD)\s*$", re.I),
    re.compile(r"^\s*(?:automatic|manual|dct|cvt)\s*$", re.I),
    re.compile(r"^\s*[LIV]\d{1,2}\s*$", re.I),
    re.compile(r"^\s*\d{3,4}\s*cc\s*$", re.I),
    re.compile(r"^\s*\d+(?:\.\d+)?\s*L\s*$", re.I),
)


def _che168_is_spec_line_noise(label: str) -> bool:
    t = label.strip()
    if not t or t.isdigit():
        return True
    low = t.lower()
    for rx in _CHE168_SPEC_LINE_NOISE_RES:
        if rx.search(t):
            return True
    noise_tokens = (
        "displacement",
        "transmission",
        "gearbox",
        "drive mode",
        "drive type",
        "engine displacement",
        "max power",
        "max torque",
        "fuel type",
        "energy type",
        "body structure",
        "length",
        "width",
        "height",
        "wheelbase",
        "curb weight",
    )
    if low in noise_tokens or (len(low) <= 3 and low in ("at", "mt", "dct", "cvt")):
        return True
    return False


_CHE168_TECH_PARAM_LABEL_FRAGMENTS: tuple[str, ...] = (
    "engine displacement",
    "max power",
    "max torque",
    "fuel consumption",
    "electric range",
    "wheelbase",
    "curb weight",
    "overall length",
    "overall width",
    "overall height",
    "body structure",
    "drive type",
    "drive mode",
    "transmission type",
    "发动机排量",
    "最大功率",
    "最大扭矩",
    "变速箱",
    "驱动方式",
    "车身结构",
)


def _che168_is_technical_param_label(name: str) -> bool:
    low = name.strip().lower()
    if not low:
        return True
    if any(f in low for f in _CHE168_TECH_PARAM_LABEL_FRAGMENTS):
        return True
    # Короткие заголовки строки параметров в блоке «основные характеристики» (не длинные маркетинговые названия).
    if len(low) <= 24 and low in (
        "transmission",
        "gearbox",
        "drive mode",
        "drive type",
        "engine",
        "fuel type",
        "energy type",
        "displacement",
    ):
        return True
    return False


def _che168_collect_from_paramtypeitems(node: Any, acc: List[str]) -> None:
    """Извлекает названия опций из блоков paramtypeitems (категории с теххарактеристиками пропускаются)."""
    if isinstance(node, dict):
        pti = node.get("paramtypeitems")
        if isinstance(pti, list):
            for type_item in pti:
                if not isinstance(type_item, dict):
                    continue
                cat = str(type_item.get("name") or "").strip()
                if _che168_is_technical_spec_category(cat):
                    continue
                for pi in type_item.get("paramitems") or []:
                    if not isinstance(pi, dict):
                        continue
                    n = pi.get("name")
                    if not isinstance(n, str) or not n.strip():
                        continue
                    ns = n.strip()
                    if _che168_is_spec_line_noise(ns) or _che168_is_technical_param_label(ns):
                        continue
                    acc.append(ns)
                for vi in type_item.get("valueitems") or []:
                    if not isinstance(vi, dict):
                        continue
                    vn = vi.get("name") or vi.get("itemname") or vi.get("title")
                    if not isinstance(vn, str) or not vn.strip():
                        continue
                    vns = vn.strip()
                    if _che168_is_spec_line_noise(vns) or _che168_is_technical_param_label(vns):
                        continue
                    acc.append(vns)
        for v in node.values():
            _che168_collect_from_paramtypeitems(v, acc)
    elif isinstance(node, list):
        for x in node:
            _che168_collect_from_paramtypeitems(x, acc)


def _dedupe_str_list_preserve_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in items:
        t = x.strip()
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _extract_real_options(specconfig: Any) -> List[str]:
    """
    Опции комплектации из /specconfig: приоритет paramtypeitems (без категорий теххарактеристик),
    иначе плоский список без «двигатель / КПП / привод» и шумовых строк.
    """
    if specconfig is None:
        return []
    acc: List[str] = []
    _che168_collect_from_paramtypeitems(specconfig, acc)
    raw = _dedupe_str_list_preserve_order(acc)
    if not raw:
        flat = _flatten_specconfig_options(specconfig)
        raw = [
            x
            for x in flat
            if not _che168_is_spec_line_noise(x) and not _che168_is_technical_param_label(x)
        ]
        raw = _dedupe_str_list_preserve_order(raw)
    return [_map_che168_option_label_ru(x) for x in raw]


def extract_che168_options_real_from_specconfig(specconfig: Any) -> List[str]:
    """Публичная обёртка для бэкфилла и скриптов."""
    return list(_extract_real_options(specconfig))


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


def _extract_power_from_engine_text(engine_text: str) -> Optional[int]:
    """Извлекает мощность из строки engine, например '1.4T 150HP L4' → 150."""
    if not engine_text:
        return None
    s = str(engine_text).strip()
    if not s:
        return None
    # Учитываем: 150HP / 150 hp / 150 л.с. / 150马力
    match = re.search(r"(\d{2,4})\s*(?:HP|hp|л\.?с\.?|马力)", s)
    if match:
        try:
            v = int(match.group(1))
            return v if 40 <= v <= 2000 else None
        except ValueError:
            return None
    return None


def _displacement_cc_from_value(v: Any) -> Optional[int]:
    if v is None:
        return None
    n = _safe_int(v)
    if n is not None and 500 <= n <= 12000:
        return n
    f = _safe_float(v)
    if f is not None and 0.5 <= f <= 8.0:
        cc = int(round(f * 1000))
        if 500 <= cc <= 12000:
            return cc
    s = str(v).strip()
    if not s:
        return None
    m_ml = re.search(r"(\d{3,5})\s*(?:ml|cc|cm3|см3|см³)", s, re.I)
    if m_ml:
        try:
            cc = int(m_ml.group(1))
            if 500 <= cc <= 12000:
                return cc
        except ValueError:
            return None
    m_l = re.search(r"(\d(?:[.,]\d)?)\s*(?:t|l)\b", s, re.I)
    if m_l:
        try:
            lit = float(m_l.group(1).replace(",", "."))
            cc = int(round(lit * 1000))
            if 500 <= cc <= 12000:
                return cc
        except ValueError:
            return None
    return None


def _displacement_cc_from_spec(spec_raw: dict) -> Optional[int]:
    for k in ("displacementml", "displacementMl", "displacement", "liter"):
        v = spec_raw.get(k)
        if v is None:
            continue
        cc = _displacement_cc_from_value(v)
        if cc is not None:
            return cc
    return None


def _spec_fields(specparam: Any) -> Dict[str, Any]:
    body = specparam
    if isinstance(specparam, dict):
        body = _unwrap_layer(specparam)
    if not isinstance(body, dict):
        return {}
    out: Dict[str, Any] = {}
    field_targets = (
        ("displacement", ("displacement", "displacementml", "displacementMl", "liter", "enginecc")),
        ("gearbox", ("gearbox", "transmission", "transmissiontype", "gearBoxType")),
        ("fueltype", ("fueltype", "fuelType", "engine", "fuel", "engineType")),
        ("drivemode", ("drivemode", "driveType", "drive", "drivetype")),
        ("bodytype", ("bodytype", "bodyType", "level", "bodyStyle", "carBodyType")),
        ("color", ("color", "bodycolor", "exteriorColor")),
        ("power", ("power", "horsepower", "maxpower", "powerhp", "maxPower")),
    )
    for key, targets in field_targets:
        for cand in _nested_dict_candidates(body):
            for t in targets:
                v = cand.get(t)
                if v is not None and str(v).strip():
                    out[key] = v
                    break
            if key in out:
                break

    label_aliases = {
        "displacement": (
            "displacement",
            "displacementl",
            "enginedisplacement",
            "enginecapacity",
            "排量",
            "发动机排量",
        ),
        "gearbox": (
            "gearbox",
            "transmission",
            "transmissiontype",
            "gear",
            "变速箱",
            "变速箱类型",
            "变速器",
        ),
        "fueltype": (
            "fueltype",
            "fuel",
            "fueltype",
            "energytype",
            "engine",
            "enginetype",
            "燃料形式",
            "发动机类型",
            "能源类型",
            "燃油类型",
            "发动机",
        ),
        "drivemode": (
            "drivemode",
            "drivetype",
            "drivetrain",
            "drive",
            "驱动方式",
            "驱动形式",
            "驱动类型",
            "驱动",
        ),
        "bodytype": ("bodytype", "body", "bodystructure", "bodystyle", "车身结构", "车体结构", "车身形式", "车身类型"),
        "power": ("power", "maxpower", "maxpowerhp", "maximumpower", "horsepower", "最大马力", "马力", "最大功率", "功率"),
    }
    norm_alias_to_key: Dict[str, str] = {}
    for key, aliases in label_aliases.items():
        for a in aliases:
            na = _norm_label_token(a)
            if na:
                norm_alias_to_key[na] = key

    name_keys = ("name", "itemname", "title", "paramname", "specname", "configName", "key", "label")
    value_keys = ("value", "dispvalue", "paramvalue", "specvalue", "subvalue", "text", "val")
    for node in _iter_deep_nodes(body):
        if not isinstance(node, dict):
            continue
        for k_raw, v in node.items():
            if v is None or not str(v).strip():
                continue
            mapped = _map_spec_alias(k_raw, norm_alias_to_key)
            if mapped and mapped not in out:
                out[mapped] = v
        n_val = None
        for nk in name_keys:
            cand = node.get(nk)
            if cand is not None and str(cand).strip():
                n_val = cand
                break
        if n_val is None:
            continue
        mapped = _map_spec_alias(n_val, norm_alias_to_key)
        if not mapped or mapped in out:
            continue
        for vk in value_keys:
            vv = node.get(vk)
            if vv is not None and str(vv).strip():
                out[mapped] = vv
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
    price_ctx = " ".join(
        str(x).strip()
        for x in (title, ci.get("subtitle"), li.get("subtitle"), ci.get("name"), li.get("name"))
        if x is not None and str(x).strip()
    )
    price_cny, price_meta = normalize_price_cny_detailed(
        raw_price,
        assume_wan_yuan=assume_price_wan_yuan,
        price_context=price_ctx,
    )

    spec_raw = _unwrap_layer(specparam) if isinstance(specparam, dict) else {}
    spec_hints = _spec_fields(spec_raw)
    opts_real = _extract_real_options(specconfig)
    opts_enriched = _flatten_specconfig_enriched(specconfig)

    displacement_label = None
    if spec_hints.get("displacement"):
        displacement_label = str(spec_hints["displacement"]).strip() or None

    dealer_flat = che168_flatten_dealer(report_summary) if report_summary else {}
    similar_raw = che168_extract_similar_ids(recommend, limit=40) if recommend else []
    similar_dedup = _dedupe_ids_preserve_order(similar_raw)
    similar_dedup = [x for x in similar_dedup if x != str(external_id)]
    disp_cc = _displacement_cc_from_spec(spec_raw) if spec_raw else None
    if disp_cc is None and spec_hints.get("displacement") is not None:
        disp_cc = _displacement_cc_from_value(spec_hints.get("displacement"))
    engine_text = ci.get("engine") or ""
    p_from_engine = _extract_power_from_engine_text(str(engine_text)) if engine_text else None
    p_hp = p_from_engine if p_from_engine is not None else _power_hp_from_hints(spec_hints)

    geo = _extract_geo(ci, li, session_cookie_hints)
    dt_fields = _extract_datetimes(ci, li)
    description = _extract_description(ci, li)
    images = _collect_image_urls(ci if ci else {}, li if li else None)
    if len(images) <= 1 and isinstance(li, dict) and li:
        dextra = _deep_collect_car_photo_urls(li)
        if len(dextra) > len(images):
            seen_m: set[str] = set(images)
            merged_im: List[str] = list(images)
            for u in dextra:
                if u not in seen_m:
                    seen_m.add(u)
                    merged_im.append(u)
            images = merged_im
    vin = _vin_from_sources(ci, li)
    yr = _year_from(ci, li)
    _cands_yr = _nested_dict_candidates(ci) + _nested_dict_candidates(li)
    yearname_s: Optional[str] = None
    regdate_s: Optional[str] = None
    for _src in _cands_yr:
        if yearname_s is None:
            yn = _src.get("yearname")
            if yn is not None and str(yn).strip():
                yearname_s = str(yn).strip()
        if regdate_s is None:
            for rk in ("regdate", "regDate", "registrationdate", "registrationDate"):
                rv = _src.get(rk)
                if rv is not None and str(rv).strip():
                    regdate_s = str(rv).strip()
                    break
        if yearname_s and regdate_s:
            break
    km_v = _mileage_km(ci, li)
    trim, trim_src = _pick_first_non_empty_with_source(
        [("carinfo", c) for c in _nested_dict_candidates(ci)] + [("list_item", c) for c in _nested_dict_candidates(li)],
        ("trimname", "trimName", "carname", "specname", "subtitle", "subTitle", "name"),
    )
    color_value, color_src = _pick_first_non_empty_with_source(
        [("spec", {"color": spec_hints.get("color")})] + [("carinfo", c) for c in _nested_dict_candidates(ci)] + [("list_item", c) for c in _nested_dict_candidates(li)],
        ("color", "bodycolor", "exteriorColor"),
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
        "yearname": yearname_s,
        "regdate": regdate_s,
        "km_age": km_v,
        "price_cny": price_cny,
        "price_on_request": bool(price_cny is None or price_cny <= 0),
        "che168_price_raw": raw_price,
        "images": images,
        "vin": vin,
        "configuration": trim,
        "color": color_value,
        "body_type": spec_hints.get("bodytype"),
        "engine_type": spec_hints.get("fueltype"),
        "transmission_type": spec_hints.get("gearbox"),
        "drive_type": spec_hints.get("drivemode"),
        "power_hp": p_hp,
        "displacement_cc": disp_cc,
        "che168_params_raw": spec_raw if spec_raw else None,
        "options_real": opts_real or None,
        "che168_recommended_options": opts_real or None,
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
    n_opt = len(opts_real) if opts_real else 0
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
    sources_used: Dict[str, str] = {}
    if color_src:
        sources_used["color"] = color_src
    if trim_src:
        sources_used["trim"] = trim_src
    if mark:
        sources_used["mark"] = "carinfo/list_item"
    if model:
        sources_used["model"] = "carinfo/list_item"
    if images:
        sources_used["images"] = "carinfo/list_item(+nested)"
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
        "field_sources": sources_used,
        "degraded_listing_data": bool(n_img <= 1 and n_spec_keys <= 2),
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
