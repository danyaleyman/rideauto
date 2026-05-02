from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from clean_mode import clean_read_enabled_for_key, clean_read_mode_enabled


def _d(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = payload.get("data")
    return raw if isinstance(raw, dict) else payload


def _clean(d: Dict[str, Any], block: str) -> Dict[str, Any]:
    v = d.get(block)
    return v if isinstance(v, dict) else {}


def _optional_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            s = v.strip().replace("\u00a0", " ").replace(" ", "").replace(",", "").replace("'", "")
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
        return float(v)
    except (TypeError, ValueError):
        return None


def _listing_denormalized_price_rub(pricing: Dict[str, Any], inner: Dict[str, Any]) -> Optional[float]:
    """Колонка cars.price_rub: приоритет final_price_rub из clean-блока, иначе my_price (без ошибки от `or` через 0.0)."""
    for cand in (_safe_float(pricing.get("final_price_rub")), _safe_float(inner.get("my_price"))):
        if cand is not None and cand > 0:
            return cand
    return None


_DISP_LABEL_RE = re.compile(r"(\d(?:\.\d)?)\s*([TL])", re.IGNORECASE)


def _displacement_cc_with_label(v: Any) -> Tuple[Optional[int], Optional[str]]:
    s = _optional_str(v)
    if not s:
        return None, None
    n = _safe_int(s)
    if n is not None:
        if 600 <= n <= 9000:
            return n, None
        return None, s
    m = _DISP_LABEL_RE.search(s)
    if not m:
        return None, s
    liters = _safe_float(m.group(1))
    if liters is None:
        return None, s
    cc = int(round(liters * 1000))
    if 600 <= cc <= 9000:
        unit = m.group(2).upper()
        return cc, f"{liters:g}{unit}"
    return None, s


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
    return _safe_int(d.get("power_hp") or d.get("hp") or d.get("outputHorsepower") or d.get("power") or d.get("horsepower"))


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
    use_clean = clean_read_enabled_for_key(str(car_id), default_enabled=clean_read_mode_enabled(default=False))
    identity = _clean(d, "identity_clean") if use_clean else {}
    spec = _clean(d, "spec_clean") if use_clean else {}
    pricing = _clean(d, "pricing_clean") if use_clean else {}
    condition = _clean(d, "condition_clean") if use_clean else {}
    src = normalized_source(d) or _optional_str((payload or {}).get("source"))
    if not src and str(car_id).lower().startswith("dongchedi-"):
        src = "dongchedi"
    if not src:
        src = "encar"
    mark = _optional_str(identity.get("mark")) or (d.get("mark") or "").strip() or None
    model = _optional_str(identity.get("model")) or (d.get("model") or "").strip() or None
    generation = _optional_str(identity.get("generation")) or _optional_str(d.get("generation") or d.get("configuration"))
    # Encar trim: только gradeName (+ clean trim); не тащить configuration/generation (Badge-дубли в generation).
    trim_grade = _optional_str(d.get("gradeName"))
    trim_identity = _optional_str(identity.get("trim_name"))
    trim_name = trim_grade or trim_identity
    if str(src).lower() != "encar":
        if not trim_name:
            trim_name = _optional_str(d.get("configuration") or d.get("generation"))

    encar_model_group = None
    if str(src).lower() == "encar":
        encar_model_group = _optional_str(d.get("modelGroupName"))
        if encar_model_group is None:
            encar_model_group = _optional_str(identity.get("model_group_encar"))
    displacement_cc, displacement_label = _displacement_cc_with_label(
        spec.get("displacement_cc") or d.get("displacement") or d.get("dongchedi_displacement_label")
    )
    ins_n, ins_krw = insurance_cases_and_payout_krw(payload)
    if ins_n is None:
        ins_n = _safe_int(condition.get("insurance_cases"))
    if ins_krw is None:
        ins_krw = _safe_int(condition.get("insurance_payout_krw"))
    ins_n_safe = 0 if ins_n is None else ins_n
    ins_krw_safe = 0 if ins_krw is None else ins_krw
    dmg_safe = damaged_parts_count(payload)
    if dmg_safe is None:
        dmg_safe = _safe_int(condition.get("damaged_parts_count"))
    if dmg_safe is None:
        dmg_safe = 0
    return {
        "car_id": car_id,
        "mark": mark,
        "model": model,
        "generation": generation,
        "trim_name": trim_name,
        "encar_model_group": encar_model_group,
        "body_type": _optional_str(spec.get("body_type")) or _optional_str(d.get("body_type")),
        "fuel_type": _optional_str(spec.get("engine_type")) or _optional_str(d.get("engine_type")),
        "transmission_type": _optional_str(spec.get("transmission_type")) or _optional_str(d.get("transmission_type")),
        "drive_type": _optional_str(spec.get("drive_type")) or _optional_str(d.get("drive_type") or d.get("prep_drive_type")),
        "color": _optional_str(spec.get("color")) or _optional_str(d.get("color")),
        "source": src,
        "listing_partition_key": listing_partition_key(car_id, d),
        "power_hp": _safe_int(spec.get("power_hp")) or power_hp(payload),
        "power_kw": _safe_int(d.get("power_kw")),
        "torque_nm": _safe_int(d.get("torque_nm")),
        "displacement_cc": displacement_cc,
        "displacement_label": displacement_label,
        "price_rub": _listing_denormalized_price_rub(pricing, d),
        "mileage_km": _safe_int(spec.get("mileage_km")) or _safe_int(d.get("km_age")),
        "year": _safe_int(identity.get("year")) or year_from_data(d),
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
    encar_model_group,
    body_type, fuel_type, transmission_type, drive_type, color,
    source, listing_partition_key,
    power_hp, power_kw, torque_nm, displacement_cc, displacement_label, price_rub, mileage_km, year, year_month,
    insurance_cases, insurance_payout_krw, insurance_payout_rub, damaged_parts_count,
    offer_created_at, data, raw, source_internal_id, created_at, updated_at
) VALUES (
    %(car_id)s, %(brand_id)s, %(model_id)s, %(mark)s, %(model)s, %(generation)s, %(trim_name)s,
    %(encar_model_group)s,
    %(body_type)s, %(fuel_type)s, %(transmission_type)s, %(drive_type)s, %(color)s,
    %(source)s, %(listing_partition_key)s,
    %(power_hp)s, %(power_kw)s, %(torque_nm)s, %(displacement_cc)s, %(displacement_label)s, %(price_rub)s, %(mileage_km)s, %(year)s, %(year_month)s,
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
    encar_model_group = EXCLUDED.encar_model_group,
    body_type = EXCLUDED.body_type,
    fuel_type = EXCLUDED.fuel_type,
    transmission_type = EXCLUDED.transmission_type,
    drive_type = EXCLUDED.drive_type,
    color = EXCLUDED.color,
    source = EXCLUDED.source,
    listing_partition_key = EXCLUDED.listing_partition_key,
    power_hp = EXCLUDED.power_hp,
    power_kw = EXCLUDED.power_kw,
    torque_nm = EXCLUDED.torque_nm,
    displacement_cc = EXCLUDED.displacement_cc,
    displacement_label = EXCLUDED.displacement_label,
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
