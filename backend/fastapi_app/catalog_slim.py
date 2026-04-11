from __future__ import annotations

import json
from typing import Any, Dict

from encar_image_order import _sort_encar_image_url_list, _sort_h_images_list_entries

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
        "gradeName",
        "gradeName_en",
        "title_en",
        "year",
        "yearMonth",
        "displacement",
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
        "images",
        "h_images",
        "color",
        "krw_per_usdt",
        "usdt_rub",
        "source",
        "price_on_request",
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


def _car_title(data: Dict[str, Any]) -> str:
    mark = (data.get("mark_en") or data.get("mark") or "").strip()
    model = (data.get("model_en") or data.get("model") or "").strip()
    generation = (
        data.get("generation_en")
        or data.get("generation")
        or data.get("configuration_en")
        or data.get("configuration")
        or ""
    ).strip()
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
        parsed = _sort_encar_image_url_list([x for x in parsed if isinstance(x, str)])
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
    p = out["price"]
    implicit_por = p is None or (isinstance(p, (int, float)) and not isinstance(p, bool) and float(p) <= 0)
    if explicit_por is True:
        out["price_on_request"] = True
    elif explicit_por is False:
        out["price_on_request"] = False
    else:
        out["price_on_request"] = implicit_por
    ca = raw.get("_catalog_created_at")
    out["catalog_created_at"] = str(ca).strip() if isinstance(ca, str) and ca.strip() else None
    out["year_num"] = int(str(slim_data.get("year") or 0)[:4] or 0)
    return out
