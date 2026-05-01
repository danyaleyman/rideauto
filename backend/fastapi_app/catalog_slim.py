from __future__ import annotations

import json
import re
from typing import Any, Dict

from encar_image_order import _sort_encar_image_url_list, _sort_h_images_list_entries
from localization.term_localizer import facet_canonical_english

_CHINA_SUFFIX_MARKERS = (
    " kuan ",
    " ban ",
    " biao ",
    " zhun ",
    " xu hang ",
    " hou qu ",
    " qian qu ",
    " si qu ",
    " zeng cheng ",
    " sheng ji ",
)
_CHINA_SUBSTRING_LABEL_OVERRIDES: Dict[str, str] = {
    "fa xian yun dong": "Discovery Sport",
    "ying lang": "Excelle GT",
    "mao xian jia": "Corsair",
    "凯迪拉克xts": "Cadillac XTS",
    "奕炫gs": "Yixuan GS",
}

_MONTHLY_PAT = re.compile(r"월\s*\d[\d,.\s]*\s*만?원")
_MONTHLY_HINT_PAT = re.compile(r"(월\s*렌트|월렌트|월\s*리스|월리스|할부|렌트|리스|대출)")
_TERM_MONTHS_PAT = re.compile(r"\d+\s*개월")


def _as_positive_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _digits_to_int(value: Any) -> int | None:
    s = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not s:
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _iter_texts(value: Any):
    if isinstance(value, str):
        s = value.strip()
        if s:
            yield s
        return
    if isinstance(value, dict):
        for vv in value.values():
            yield from _iter_texts(vv)
        return
    if isinstance(value, list):
        for vv in value:
            yield from _iter_texts(vv)
        return


def _encar_finance_like_card(data: Dict[str, Any]) -> bool:
    src = str(data.get("source") or "encar").strip().lower()
    if src != "encar":
        return False
    if data.get("encar_monthly_finance_price") is True:
        return True
    monthly_keys = ("encar_month_lease_price", "encar_month_lease_rent_price", "encar_month_lease_rest")
    if any(_as_positive_float(data.get(k)) > 0 for k in monthly_keys):
        return True
    for s in _iter_texts(data):
        if _MONTHLY_PAT.search(s):
            return True
        # Generic finance words can appear on normal cards; require monthly/term context.
        if _MONTHLY_HINT_PAT.search(s) and ("월" in s or _TERM_MONTHS_PAT.search(s)):
            return True
        if _TERM_MONTHS_PAT.search(s) and ("렌트" in s or "리스" in s or "할부" in s):
            return True
        if "차량가격" in s and ("월" in s or _MONTHLY_HINT_PAT.search(s)):
            return True

    # Last-resort guard: implausibly low Encar sale price for modern/low-mileage cars.
    pw = _as_positive_float(data.get("price_won"))
    p_mw = _as_positive_float(data.get("price"))
    eff_mw = p_mw if p_mw > 0 else (pw / 10000.0 if pw > 0 else 0.0)
    year_val = _digits_to_int(str(data.get("year") or data.get("yearMonth") or "")[:4])
    km_val = _digits_to_int(data.get("km_age"))
    if 0 < eff_mw < 1000 and ((year_val is not None and year_val >= 2015) or (km_val is not None and km_val <= 150000)):
        return True
    return False


def _coerce_catalog_images_to_urls(parsed: list[Any]) -> list[str]:
    """Slim-каталог: в `images` могут быть строки (Encar/DC) или dict с url/pic_url — как в сыром API."""
    out: list[str] = []
    for x in parsed:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
            continue
        if not isinstance(x, dict):
            continue
        u = (
            x.get("url")
            or x.get("image")
            or x.get("image_url")
            or x.get("pic_url")
            or x.get("picUrl")
            or x.get("big_url")
            or x.get("bigUrl")
            or x.get("thumb_url")
            or x.get("thumbUrl")
            or x.get("cover_url")
            or x.get("coverUrl")
        )
        if isinstance(u, str) and u.strip().startswith("http"):
            out.append(u.strip())
    return out

_SLIM_CATALOG_DATA_KEYS = frozenset(
    {
        "mark",
        "mark_en",
        "model",
        "model_en",
        "generation",
        "generation_en",
        "configuration",
        "configuration_en",
        "trim_name",
        "trim_name_en",
        "gradeName",
        "gradeName_en",
        "title_en",
        "year",
        "yearMonth",
        "displacement",
        "dongchedi_displacement_label",
        "dongchedi_params_raw",
        "engine_type",
        "drive_type",
        "prep_drive_type",
        "body_type",
        "transmission_type",
        "km_age",
        "offer_created",
        "created_at",
        "url",
        "inner_id",
        "my_price",
        "price_won",
        "price_calc_failed",
        "power",
        "hp",
        "outputHorsepower",
        "power_hp",
        "power_kw",
        "torque_nm",
        "images",
        "h_images",
        "color",
        "krw_per_usdt",
        "usdt_rub",
        "source",
        "price_on_request",
        "price_text",
        "encar_price_type",
        "encar_price_type_name",
        "encar_lease_type",
        "encar_attribute_type",
        "encar_monthly_finance_price",
        "encar_month_lease_price",
        "encar_month_lease_rent_price",
        "encar_month_lease_rest",
    }
)


def _extract_num(data: Dict[str, Any], key: str) -> float | None:
    try:
        value = data.get(key)
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _cleanup_china_model_name(name: str) -> str:
    s = " ".join(str(name or "").split()).strip()
    if not s:
        return ""
    low0 = s.lower()
    for needle, repl in _CHINA_SUBSTRING_LABEL_OVERRIDES.items():
        if needle in low0:
            s = re.sub(re.escape(needle), repl, s, flags=re.IGNORECASE)
            low0 = s.lower()
    low = f" {s.lower()} "
    cut = None
    for marker in _CHINA_SUFFIX_MARKERS:
        idx = low.find(marker)
        if idx > 0:
            cut = idx if cut is None else min(cut, idx)
    if cut is not None:
        s = s[:cut].strip()
    m = re.search(r"\b20\d{2}\b", s)
    if m and m.start() > 0:
        s = s[: m.start()].strip()
    s = " ".join(re.sub(r"[\u4e00-\u9fff\uac00-\ud7af]+", " ", s).split())
    return s


def _car_title(data: Dict[str, Any]) -> str:
    def _pick(en_key: str, raw_key: str, domain: str) -> str:
        t = (data.get(en_key) or "").strip()
        if t:
            return t
        raw = data.get(raw_key)
        c = facet_canonical_english(raw, domain).strip()
        if c:
            return c
        return (raw or "").strip() if isinstance(raw, str) else ""

    mark = _pick("mark_en", "mark", "mark")
    model = _pick("model_en", "model", "model")
    source = (data.get("source") or "").strip().lower()
    if source == "dongchedi" or source == "china":
        model = _cleanup_china_model_name(model) or model
        if mark and model and model.lower().startswith(mark.lower()):
            return model
        return " ".join([x for x in [mark, model] if x]).strip()
    generation = (
        (data.get("generation_en") or "").strip()
        or facet_canonical_english(data.get("generation"), "generation").strip()
        or (data.get("generation") or "").strip()
        or (data.get("configuration_en") or "").strip()
        or facet_canonical_english(data.get("configuration"), "configuration").strip()
        or (data.get("configuration") or "").strip()
    )
    return " ".join([x for x in [mark, model, generation] if x]).strip()


def _trim_slim_list_field(slim_data: Dict[str, Any], key: str, max_items: int) -> None:
    if max_items < 1 or key not in slim_data:
        return
    v = slim_data[key]
    parsed: Any = None
    as_string = False
    if isinstance(v, str):
        as_string = True
        try:
            parsed = json.loads(v)
        except Exception:
            return
    elif isinstance(v, list):
        parsed = v
    else:
        return
    if not isinstance(parsed, list) or not parsed:
        return
    if key == "images":
        parsed = _sort_encar_image_url_list(_coerce_catalog_images_to_urls(parsed))
    elif key == "h_images":
        parsed = _sort_h_images_list_entries([x for x in parsed if isinstance(x, dict)])
    if len(parsed) > max_items:
        parsed = parsed[:max_items]
    slim_data[key] = json.dumps(parsed, ensure_ascii=False) if as_string else parsed


def slim_catalog_car(car: Dict[str, Any], car_id: str) -> Dict[str, Any]:
    raw = car.get("data") if isinstance(car.get("data"), dict) else None
    if not isinstance(raw, dict):
        raw = car if isinstance(car, dict) else {}
    slim_data: Dict[str, Any] = {k: raw[k] for k in _SLIM_CATALOG_DATA_KEYS if k in raw}
    _trim_slim_list_field(slim_data, "images", 12)
    _trim_slim_list_field(slim_data, "h_images", 18)
    inner = raw.get("inner_id") if raw.get("inner_id") not in (None, "") else car.get("inner_id")
    if inner is not None and inner != "":
        slim_data["inner_id"] = inner
    out: Dict[str, Any] = {"id": car_id, "data": slim_data}
    _tid = car.get("inner_id") or slim_data.get("inner_id")
    if _tid is not None and _tid != "":
        out["inner_id"] = _tid
    out["title"] = _car_title(slim_data)
    out["price"] = _extract_num(slim_data, "my_price")
    explicit_por = slim_data.get("price_on_request")
    forced_por = _encar_finance_like_card(slim_data)
    if forced_por:
        out["price"] = None
    p = out["price"]
    implicit_por = p is None or (isinstance(p, (int, float)) and not isinstance(p, bool) and float(p) <= 0)
    if forced_por:
        out["price_on_request"] = True
    elif explicit_por is True:
        out["price_on_request"] = True
    elif explicit_por is False:
        out["price_on_request"] = False
    else:
        out["price_on_request"] = implicit_por
    ca = raw.get("_catalog_created_at")
    out["catalog_created_at"] = str(ca).strip() if isinstance(ca, str) and ca.strip() else None
    out["year_num"] = int(str(slim_data.get("year") or 0)[:4] or 0)
    if car.get("encar_listing_sold") is True:
        out["encar_listing_sold"] = True
    if raw.get("encar_listing_reserved") is True or car.get("encar_listing_reserved") is True:
        out["encar_listing_reserved"] = True
    if car.get("dongchedi_listing_sold") is True:
        out["dongchedi_listing_sold"] = True
    return out
