from __future__ import annotations

from typing import Any, Dict

from clean_mode import legacy_fallbacks_enabled

_VALID_TIERS = frozenset({"full_customs", "korea_land_only", "price_on_request"})


def _pricing_tier_resolve(data: Dict[str, Any], pricing: Dict[str, Any]) -> str:
    tv = pricing.get("pricing_tier") if isinstance(pricing, dict) else None
    if isinstance(tv, str) and tv in _VALID_TIERS:
        return tv
    if isinstance(data.get("pricing_tier"), str) and data.get("pricing_tier") in _VALID_TIERS:
        return str(data.get("pricing_tier"))
    legacy_por = bool(_pick(pricing, "price_on_request", data, "price_on_request") is True)
    if legacy_por:
        return "price_on_request"
    # Данные до encar pricing_tier в JSON: ведём себя как полный расчёт таможни
    return "full_customs"


def _customs_included_for_tier(tier: str, pricing: Dict[str, Any]) -> bool:
    if isinstance(pricing, dict) and isinstance(pricing.get("customs_included"), bool):
        return bool(pricing.get("customs_included"))
    return tier == "full_customs"


def _safe_text(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _safe_num(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _pick(clean: Dict[str, Any], key: str, legacy: Dict[str, Any], legacy_key: str) -> Any:
    if key in clean and clean.get(key) not in (None, ""):
        return clean.get(key)
    if legacy_fallbacks_enabled(default=True):
        return legacy.get(legacy_key)
    return None


def build_catalog_read_model(data: Dict[str, Any], *, use_clean: bool) -> Dict[str, Any]:
    # Postgres `cars.data` часто сохранён как `{ "inner_id": "…", "data": { …карточка… } }` с parser.
    inner = data.get("data")
    if isinstance(inner, dict) and (
        isinstance(inner.get("pricing_clean"), dict)
        or isinstance(inner.get("identity_clean"), dict)
        or isinstance(inner.get("mark"), str)
        or isinstance(inner.get("pricing_tier"), str)
    ):
        data = inner

    identity = data.get("identity_clean") if use_clean and isinstance(data.get("identity_clean"), dict) else {}
    spec = data.get("spec_clean") if use_clean and isinstance(data.get("spec_clean"), dict) else {}
    pricing = data.get("pricing_clean") if use_clean and isinstance(data.get("pricing_clean"), dict) else {}
    condition = data.get("condition_clean") if use_clean and isinstance(data.get("condition_clean"), dict) else {}

    tier = _pricing_tier_resolve(data, pricing)
    customs_included = _customs_included_for_tier(tier, pricing)
    numeric_price_rub = _safe_num(_pick(pricing, "final_price_rub", data, "my_price"))

    legacy_reserved = bool(
        _pick(pricing, "reserved_placeholder", data, "encar_listing_reserved") is True,
    )
    price_on_request = tier == "price_on_request"
    price_out: float | None = None if tier == "price_on_request" else numeric_price_rub

    return {
        "mark": _safe_text(_pick(identity, "mark", data, "mark")),
        "model": _safe_text(_pick(identity, "model", data, "model")),
        "generation": _safe_text(_pick(identity, "generation", data, "generation")),
        "trim_name": _safe_text(_pick(identity, "trim_name", data, "trim_name")),
        "year": _pick(identity, "year", data, "year"),
        "engine_type": _safe_text(_pick(spec, "engine_type", data, "engine_type")),
        "transmission_type": _safe_text(_pick(spec, "transmission_type", data, "transmission_type")),
        "drive_type": _safe_text(_pick(spec, "drive_type", data, "drive_type")),
        "body_type": _safe_text(_pick(spec, "body_type", data, "body_type")),
        "color": _safe_text(_pick(spec, "color", data, "color")),
        "mileage_km": _pick(spec, "mileage_km", data, "km_age"),
        "power_hp": _pick(spec, "power_hp", data, "power_hp"),
        "price_rub": price_out,
        "price_on_request": price_on_request,
        "reserved_placeholder": legacy_reserved,
        "pricing_tier": tier,
        "customs_included": customs_included,
        "insurance_cases": _pick(condition, "insurance_cases", data, "insurance_cases"),
        "damaged_parts_count": _pick(condition, "damaged_parts_count", data, "damaged_parts_count"),
    }


def build_car_detail_read_model(row: Dict[str, Any], *, use_clean: bool, api_version: str) -> Dict[str, Any]:
    data = row.get("data") if isinstance(row.get("data"), dict) else row
    rm = build_catalog_read_model(data, use_clean=use_clean)
    out = dict(row)
    out["read_model_version"] = f"car_detail.{api_version}"
    out["read_model"] = rm
    return out

