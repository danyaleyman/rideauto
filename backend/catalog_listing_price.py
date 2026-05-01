"""Правила «есть ли цена в объявлении» и очистка полей расчёта для режима «цена по запросу»."""
from __future__ import annotations

import re
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
    def _is_repeated_placeholder_4d(mw4: str) -> bool:
        # 1111/2222/.../9999 and softened variant 1110/2220/.../9990 in 만원 units.
        d = "".join(ch for ch in str(mw4) if ch.isdigit())
        if len(d) != 4 or d[0] == "0":
            return False
        if len(set(d)) == 1:
            return True
        return d[0] == d[1] == d[2] and d[3] == "0"

    def _looks_like_placeholder_won_digits(digits: str) -> bool:
        d = "".join(ch for ch in str(digits) if ch.isdigit())
        if not d:
            return False
        if _is_repeated_placeholder_4d(d):
            return True
        # Full-won form (e.g. 44_440_000 / 99_990_000) => strip trailing 만원 zeros.
        if len(d) >= 8 and d.endswith("0000"):
            lead = d[:-4]
            if len(lead) >= 4 and _is_repeated_placeholder_4d(lead[:4]):
                return True
        return False

    pw = data.get("price_won")
    try:
        if pw is not None:
            pw_digits = "".join(ch for ch in str(int(float(pw))) if ch.isdigit())
            if _looks_like_placeholder_won_digits(pw_digits):
                return True
    except (TypeError, ValueError):
        pass

    p = data.get("price")
    if p is None:
        return False
    return _looks_like_placeholder_won_digits(str(p))


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

    monthly_pat = re.compile(r"월\s*\d[\d,.\s]*\s*만?원")
    monthly_keyword_pat = re.compile(r"(월\s*렌트|월렌트|월\s*리스|월리스|할부|렌트|리스|대출)")
    term_pat = re.compile(r"\d+\s*개월")
    takeover_pat = re.compile(r"인수금\s*\d[\d,.\s]*\s*만?원")

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
        if monthly_pat.search(s) or monthly_keyword_pat.search(s) or takeover_pat.search(s):
            return True
        if term_pat.search(s) and ("렌트" in s or "리스" in s or "할부" in s):
            return True
        # Типичный блок Encar finance card: 월xx만원 + 월렌트(12개월) + 인수금/차량가격.
        if "차량가격" in s and ("월" in s or monthly_keyword_pat.search(s) or term_pat.search(s)):
            return True

    for s in _iter_texts(data):
        low = s.lower()
        if "lease" in low or "rent" in low:
            return True
        if monthly_pat.search(s) or takeover_pat.search(s):
            return True
        if monthly_keyword_pat.search(s) and ("월" in s or term_pat.search(s)):
            return True
        if "차량가격" in s and ("월" in s or monthly_keyword_pat.search(s)):
            return True
    # Legacy fallback: some older rows store monthly payment in `price_won` directly
    # (e.g. 24, 33) without explicit lease flags. Real sale prices on Encar are not that low.
    if str(data.get("source") or "encar").strip().lower() == "encar":
        pw = _as_positive_float(data.get("price_won"))
        p = _as_positive_float(data.get("price"))
        if 0 < pw < 100 and p < 10000:
            return True
    if _encar_suspicious_low_sale_price(data):
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
