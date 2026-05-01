from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

PriceIntent = Literal["sale", "monthly_finance", "reserved_placeholder", "unknown"]

_MONTHLY_AMOUNT_RE = re.compile(r"월\s*\d[\d,.\s]*\s*만?원")
_MONTHLY_HINT_RE = re.compile(r"(월\s*렌트|월렌트|월\s*리스|월리스|렌트|리스|할부|대출)")
_TERM_MONTHS_RE = re.compile(r"\d+\s*개월")
_TAKEOVER_RE = re.compile(r"인수금\s*\d[\d,.\s]*\s*만?원")


def _as_positive_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _is_repeated_or_soft_4d(d4: str) -> bool:
    d = _digits(d4)
    if len(d) != 4 or d[0] == "0":
        return False
    return (d[0] == d[1] == d[2] == d[3]) or (d[0] == d[1] == d[2] and d[3] == "0")


def _looks_placeholder(price_mw: Any, price_won: Any) -> bool:
    p4 = _digits(price_mw)
    if _is_repeated_or_soft_4d(p4):
        return True
    pw = _digits(price_won)
    if _is_repeated_or_soft_4d(pw):
        return True
    if len(pw) >= 8 and pw.endswith("0000"):
        lead = pw[:-4]
        if len(lead) >= 4 and _is_repeated_or_soft_4d(lead[:4]):
            return True
    return False


def _iter_texts(value: Any) -> Iterable[str]:
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


def _monthly_signals(texts: Iterable[str]) -> List[str]:
    sig: List[str] = []
    for s in texts:
        if _MONTHLY_AMOUNT_RE.search(s):
            sig.append("monthly_amount")
        if _TAKEOVER_RE.search(s):
            sig.append("takeover_amount")
        if _MONTHLY_HINT_RE.search(s) and ("월" in s or _TERM_MONTHS_RE.search(s)):
            sig.append("monthly_hint_context")
        if _TERM_MONTHS_RE.search(s) and ("렌트" in s or "리스" in s or "할부" in s):
            sig.append("term_plus_finance_word")
        if "차량가격" in s and ("월" in s or _MONTHLY_HINT_RE.search(s)):
            sig.append("price_in_monthly_context")
    return sorted(set(sig))


def classify_encar_price_intent(
    payload: Optional[Dict[str, Any]],
    *,
    extra_texts: Optional[Iterable[str]] = None,
) -> Tuple[PriceIntent, List[str]]:
    if not isinstance(payload, dict):
        return "unknown", []
    src = str(payload.get("source") or "encar").strip().lower()
    if src != "encar":
        return "unknown", []

    signals: List[str] = []
    if payload.get("encar_monthly_finance_price") is True:
        signals.append("monthly_flag_true")
    monthly_keys = ("encar_month_lease_price", "encar_month_lease_rent_price", "encar_month_lease_rest")
    if any(_as_positive_float(payload.get(k)) > 0 for k in monthly_keys):
        signals.append("monthly_numeric_keys")

    text_sources: List[str] = [
        str(payload.get("price_text") or ""),
        str(payload.get("encar_lease_type") or ""),
        str(payload.get("encar_attribute_type") or ""),
        str(payload.get("encar_price_type_name") or ""),
        str(payload.get("encar_price_type") or ""),
        str(payload.get("finance_type") or ""),
    ]
    if extra_texts:
        text_sources.extend(str(x or "") for x in extra_texts)
    signals.extend(_monthly_signals(text_sources))

    if _looks_placeholder(payload.get("price"), payload.get("price_won")):
        signals.append("reserved_placeholder_digits")
        return "reserved_placeholder", sorted(set(signals))

    if signals:
        return "monthly_finance", sorted(set(signals))

    # Legacy fallback: tiny won amount is typically monthly payment.
    pw = _as_positive_float(payload.get("price_won"))
    p = _as_positive_float(payload.get("price"))
    if 0 < pw < 100 and p < 10000:
        return "monthly_finance", ["legacy_small_won_payment"]

    # Suspiciously low sale price for modern/low-mileage cars (common finance bait).
    eff_mw = p if p > 0 else (pw / 10000.0 if pw > 0 else 0.0)
    year_digits = _digits(str(payload.get("year") or payload.get("yearMonth") or "")[:4])
    year_val = int(year_digits) if year_digits else None
    km_digits = _digits(payload.get("km_age"))
    km_val = int(km_digits) if km_digits else None
    if 0 < eff_mw < 1000 and ((year_val is not None and year_val >= 2015) or (km_val is not None and km_val <= 150000)):
        return "monthly_finance", ["suspicious_low_sale_price"]

    if pw > 0 or p > 0:
        return "sale", []
    return "unknown", []


def price_signals_json(signals: List[str]) -> str:
    try:
        return json.dumps(sorted(set(signals)), ensure_ascii=False)
    except Exception:
        return "[]"

