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
    "china_docs_delivery_cny",
    "china_docs_delivery_rub",
    "cny_rub",
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
    if _encar_monthly_finance_payload(data):
        return False
    if encar_reserved_placeholder_price(data):
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
    pw = data.get("price_won")
    try:
        if pw is not None:
            pw_digits = "".join(ch for ch in str(int(float(pw))) if ch.isdigit())
            if len(pw_digits) == 4 and len(set(pw_digits)) == 1:
                return True
            # Часто в данных уже хранится полный won (например 99_990_000, 111_110_000),
            # где первые 4 цифры — заглушка 9999만원/5555만원/1111만원 и т.п.
            if len(pw_digits) >= 8 and pw_digits.endswith("0000"):
                lead = pw_digits[:-4]
                if len(lead) >= 4 and len(set(lead[:4])) == 1:
                    return True
    except (TypeError, ValueError):
        pass

    p = data.get("price")
    if p is None:
        return False
    digits = "".join(ch for ch in str(p) if ch.isdigit())
    return len(digits) == 4 and len(set(digits)) == 1


def _as_positive_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _encar_monthly_finance_payload(data: Dict[str, Any]) -> bool:
    if data.get("encar_monthly_finance_price") is True:
        return True
    monthly_keys = ("encar_month_lease_price", "encar_month_lease_rent_price", "encar_month_lease_rest")
    if any(_as_positive_float(data.get(k)) > 0 for k in monthly_keys):
        return True
    hint_keys = (
        "encar_lease_type",
        "encar_attribute_type",
        "price_type",
        "price_type_name",
        "finance_type",
        "price_text",
    )
    for k in hint_keys:
        s = str(data.get(k) or "").strip().lower()
        if not s:
            continue
        if "lease" in s or "rent" in s or "리스" in s or "렌트" in s or "할부" in s or "월" in s:
            return True
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


def dongchedi_has_source_price(data: Optional[Dict[str, Any]]) -> bool:
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
