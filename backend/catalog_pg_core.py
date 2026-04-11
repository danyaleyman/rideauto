from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List, Optional, Tuple


def _d(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = payload.get("data")
    return raw if isinstance(raw, dict) else payload


def _optional_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None or v == "":
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def extract_image_urls(payload: Dict[str, Any]) -> List[str]:
    raw = _d(payload).get("images")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def listing_partition_key(car_id: str, data: Dict[str, Any]) -> str:
    return str(data.get("inner_id") or data.get("id") or car_id).strip()


def normalized_source(data: Dict[str, Any]) -> Optional[str]:
    return _optional_str(data.get("source"))


def year_from_data(data: Dict[str, Any]) -> Optional[int]:
    y = _safe_int(data.get("year"))
    if y:
        return y
    ym = _optional_str(data.get("yearMonth")) or _optional_str(data.get("year_month"))
    if ym and len(ym) >= 4 and ym[:4].isdigit():
        return int(ym[:4])
    return None


def year_month_ordinal(data: Dict[str, Any]) -> Optional[int]:
    ym = _optional_str(data.get("yearMonth")) or _optional_str(data.get("year_month"))
    if ym and len(ym) >= 7 and ym[4] == "-" and ym[:4].isdigit() and ym[5:7].isdigit():
        return int(ym[:4]) * 100 + int(ym[5:7])
    return None


def power_hp(payload: Dict[str, Any]) -> Optional[int]:
    d = _d(payload)
    return _safe_int(d.get("power") or d.get("horsepower"))


def offer_created_at(payload: Dict[str, Any]) -> Optional[datetime]:
    d = _d(payload)
    s = _optional_str(d.get("created_at") or d.get("modifiedDate"))
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def insurance_cases_and_payout_krw(payload: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    d = _d(payload)
    return _safe_int(d.get("insurance_count")), _safe_int(d.get("insurance_amount"))


def insurance_payout_rub(data: Dict[str, Any], payout_krw: Optional[int]) -> Optional[float]:
    if payout_krw is None:
        return None
    fx = _safe_float(data.get("krw_to_rub") or 0.06)
    return payout_krw * (fx or 0.06)


def damaged_parts_count(payload: Dict[str, Any]) -> Optional[int]:
    d = _d(payload)
    return _safe_int(d.get("damaged_parts_count"))


def get_or_create_brand(cur: Any, cache: Dict[str, int], name: Optional[str]) -> Optional[int]:
    name = (name or "").strip()
    if not name:
        return None
    key = name.lower()
    if key in cache:
        return cache[key]
    cur.execute(
        "INSERT INTO brands (name) VALUES (%s) ON CONFLICT (name_norm) DO NOTHING RETURNING id",
        (name,),
    )
    row = cur.fetchone()
    if row:
        bid = int(row[0])
    else:
        cur.execute("SELECT id FROM brands WHERE name_norm = lower(trim(%s))", (name,))
        r2 = cur.fetchone()
        bid = int(r2[0]) if r2 else None
    if bid is None:
        raise RuntimeError(f"brand upsert failed for {name!r}")
    cache[key] = bid
    return bid


def get_or_create_model(cur: Any, cache: Dict[Tuple[int, str], int], brand_id: int, name: Optional[str]) -> Optional[int]:
    name = (name or "").strip()
    if not name:
        return None
    key = (brand_id, name.lower())
    if key in cache:
        return cache[key]
    cur.execute(
        """
        INSERT INTO models (brand_id, name) VALUES (%s, %s)
        ON CONFLICT (brand_id, name_norm) DO NOTHING RETURNING id
        """,
        (brand_id, name),
    )
    row = cur.fetchone()
    if row:
        mid = int(row[0])
    else:
        cur.execute(
            "SELECT id FROM models WHERE brand_id = %s AND name_norm = lower(trim(%s))",
            (brand_id, name),
        )
        r2 = cur.fetchone()
        mid = int(r2[0]) if r2 else None
    if mid is None:
        raise RuntimeError(f"model upsert failed for brand_id={brand_id} name={name!r}")
    cache[key] = mid
    return mid


def row_to_car_fields(
    car_id: str,
    payload: Dict[str, Any],
    *,
    source_internal_id: Optional[int] = None,
) -> Dict[str, Any]:
    d = _d(payload)
    src = normalized_source(d) or _optional_str((payload or {}).get("source"))
    if not src and str(car_id).lower().startswith("dongchedi-"):
        src = "dongchedi"
    if not src:
        src = "encar"
    mark = (d.get("mark") or "").strip() or None
    model = (d.get("model") or "").strip() or None
    generation = _optional_str(d.get("generation") or d.get("configuration"))
    trim_name = _optional_str(d.get("gradeName") or d.get("configuration") or d.get("generation"))
    ins_n, ins_krw = insurance_cases_and_payout_krw(payload)
    ins_n_safe = 0 if ins_n is None else ins_n
    ins_krw_safe = 0 if ins_krw is None else ins_krw
    dmg_safe = damaged_parts_count(payload)
    if dmg_safe is None:
        dmg_safe = 0
    return {
        "car_id": car_id,
        "mark": mark,
        "model": model,
        "generation": generation,
        "trim_name": trim_name,
        "body_type": _optional_str(d.get("body_type")),
        "fuel_type": _optional_str(d.get("engine_type")),
        "transmission_type": _optional_str(d.get("transmission_type")),
        "drive_type": _optional_str(d.get("drive_type") or d.get("prep_drive_type")),
        "color": _optional_str(d.get("color")),
        "source": src,
        "listing_partition_key": listing_partition_key(car_id, d),
        "power_hp": power_hp(payload),
        "displacement_cc": _safe_int(d.get("displacement")),
        "price_rub": _safe_float(d.get("my_price")),
        "mileage_km": _safe_int(d.get("km_age")),
        "year": year_from_data(d),
        "year_month": year_month_ordinal(d),
        "insurance_cases": ins_n_safe,
        "insurance_payout_krw": ins_krw_safe,
        "insurance_payout_rub": insurance_payout_rub(d, ins_krw_safe),
        "damaged_parts_count": dmg_safe,
        "offer_created_at": offer_created_at(payload),
        "source_internal_id": source_internal_id,
    }


UPSERT_CAR_SQL = """
INSERT INTO cars (
    car_id, brand_id, model_id, mark, model, generation, trim_name,
    body_type, fuel_type, transmission_type, drive_type, color,
    source, listing_partition_key,
    power_hp, displacement_cc, price_rub, mileage_km, year, year_month,
    insurance_cases, insurance_payout_krw, insurance_payout_rub, damaged_parts_count,
    offer_created_at, data, raw, source_internal_id, created_at, updated_at
) VALUES (
    %(car_id)s, %(brand_id)s, %(model_id)s, %(mark)s, %(model)s, %(generation)s, %(trim_name)s,
    %(body_type)s, %(fuel_type)s, %(transmission_type)s, %(drive_type)s, %(color)s,
    %(source)s, %(listing_partition_key)s,
    %(power_hp)s, %(displacement_cc)s, %(price_rub)s, %(mileage_km)s, %(year)s, %(year_month)s,
    %(insurance_cases)s, %(insurance_payout_krw)s, %(insurance_payout_rub)s, %(damaged_parts_count)s,
    %(offer_created_at)s, %(data)s, %(raw)s,
    %(source_internal_id)s, COALESCE(%(created_at)s, now()), now()
)
ON CONFLICT (car_id) DO UPDATE SET
    brand_id = EXCLUDED.brand_id,
    model_id = EXCLUDED.model_id,
    mark = EXCLUDED.mark,
    model = EXCLUDED.model,
    generation = EXCLUDED.generation,
    trim_name = EXCLUDED.trim_name,
    body_type = EXCLUDED.body_type,
    fuel_type = EXCLUDED.fuel_type,
    transmission_type = EXCLUDED.transmission_type,
    drive_type = EXCLUDED.drive_type,
    color = EXCLUDED.color,
    source = EXCLUDED.source,
    listing_partition_key = EXCLUDED.listing_partition_key,
    power_hp = EXCLUDED.power_hp,
    displacement_cc = EXCLUDED.displacement_cc,
    price_rub = EXCLUDED.price_rub,
    mileage_km = EXCLUDED.mileage_km,
    year = EXCLUDED.year,
    year_month = EXCLUDED.year_month,
    insurance_cases = EXCLUDED.insurance_cases,
    insurance_payout_krw = EXCLUDED.insurance_payout_krw,
    insurance_payout_rub = EXCLUDED.insurance_payout_rub,
    damaged_parts_count = EXCLUDED.damaged_parts_count,
    offer_created_at = EXCLUDED.offer_created_at,
    data = EXCLUDED.data,
    raw = EXCLUDED.raw,
    source_internal_id = EXCLUDED.source_internal_id,
    updated_at = now()
RETURNING id
"""
