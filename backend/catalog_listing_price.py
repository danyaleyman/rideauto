"""Правила «есть ли цена в объявлении» и очистка полей расчёта для режима «цена по запросу»."""
from __future__ import annotations

from typing import Any, Dict, Optional

_FIELDS_FROM_KOREAN_PRICE_CALC = (
    "my_price",
    "price_rub_estimate",
    "documents_krw_rub",
    "freight_rub",
    "customs_fee_rub",
    "duty_rub",
    "excise_rub",
    "util_rub",
    "vat_rub",
    "customs_total_rub",
    "broker_rub",
    "commission_rub",
    "vehicle_sum_rub",
    "krw_per_usdt",
    "usdt_rub",
    "commission_rate_effective",
    "commission_rate_default",
    "price_calc_failed",
)


def china_market_car(car_id: str, data: Optional[Dict[str, Any]]) -> bool:
    if str(car_id or "").lower().startswith("dongchedi-"):
        return True
    if isinstance(data, dict) and str(data.get("source") or "").strip().lower() == "dongchedi":
        return True
    return False


def encar_has_list_price(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False
    pw = data.get("price_won")
    try:
        if pw is not None and float(pw) > 0:
            return True
    except (TypeError, ValueError):
        pass
    p = data.get("price")
    try:
        if p is None or p == "":
            return False
        v = int(float(str(p).replace(" ", "").replace(",", ".")))
        return v > 0
    except (TypeError, ValueError):
        return False


def dongchedi_has_buyer_price(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False
    mp = data.get("my_price")
    try:
        if mp is not None and float(mp) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def clear_estimated_price_fields(data: Dict[str, Any]) -> None:
    for k in _FIELDS_FROM_KOREAN_PRICE_CALC:
        data.pop(k, None)
