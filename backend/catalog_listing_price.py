"""Правила «есть ли цена в объявлении» и очистка полей расчёта для режима «цена по запросу»."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from encar_price_intent import classify_encar_price_intent

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
    "china_docs_delivery_cny",
    "china_docs_delivery_rub",
    "vtb_bank_transfer_rub",
    "cny_rub",
    "price_calc_failed",
)


def china_market_car(car_id: str, data: Optional[Dict[str, Any]]) -> bool:
    if str(car_id or "").lower().startswith("che168-"):
        return True
    if isinstance(data, dict):
        src = str(data.get("source") or "").strip().lower()
        if src in ("che168", "china"):
            return True
    return False


def encar_has_list_price(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False
    intent, _ = classify_encar_price_intent(data)
    if intent in ("monthly_finance", "reserved_placeholder"):
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


def encar_reserved_placeholder_price(data: Optional[Dict[str, Any]]) -> bool:
    """
    На Encar забронированные/выкупленные авто нередко помечаются «заглушкой» вида
    9,999만원 / 4,444만원 (четыре одинаковые цифры в цене объявления).
    Такие значения нельзя использовать для расчета итоговой стоимости.
    """
    if not isinstance(data, dict):
        return False
    intent, _ = classify_encar_price_intent(data)
    return intent == "reserved_placeholder"


def _as_positive_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _digits_to_int(value: Any) -> Optional[int]:
    s = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not s:
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _encar_suspicious_low_sale_price(data: Dict[str, Any]) -> bool:
    """
    Aggressive fallback for Encar finance cards:
    even with missing text markers, prices like 432만원 for near-new cars are usually lease/credit blocks.
    """
    if str(data.get("source") or "encar").strip().lower() != "encar":
        return False
    pw = _as_positive_float(data.get("price_won"))
    p_mw = _as_positive_float(data.get("price"))  # 만원 unit in parser payload
    eff_mw = p_mw if p_mw > 0 else (pw / 10000.0 if pw > 0 else 0.0)
    if not (0 < eff_mw < 1000):
        return False

    year_raw = str(data.get("year") or data.get("yearMonth") or "").strip()
    year_val = _digits_to_int(year_raw[:4]) if year_raw else None
    km_val = _digits_to_int(data.get("km_age"))

    # For modern/low-mileage cars such low advertised sale price is almost always finance bait.
    if year_val is not None and year_val >= 2015:
        return True
    if km_val is not None and km_val <= 150000:
        return True
    return False


def _encar_monthly_finance_payload(data: Dict[str, Any]) -> bool:
    intent, _ = classify_encar_price_intent(data)
    return intent == "monthly_finance"


def china_has_buyer_price(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False
    mp = data.get("my_price")
    try:
        if mp is not None and float(mp) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def china_has_source_price(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False
    p = data.get("price_cny")
    try:
        if p is not None and float(p) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def clear_estimated_price_fields(data: Dict[str, Any]) -> None:
    for k in _FIELDS_FROM_KOREAN_PRICE_CALC:
        data.pop(k, None)
