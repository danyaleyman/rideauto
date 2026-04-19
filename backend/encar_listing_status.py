"""
Статус объявления Encar по ответу readside API ``/vehicle/{id}`` (как в парсере / daily_update).
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def _sales_status_strings(detail: Dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("salesStatus", "SalesStatus", "saleStatus"):
        v = detail.get(key)
        if v is not None and str(v).strip():
            parts.append(str(v))
    adv = detail.get("advertisement")
    if isinstance(adv, dict):
        for key in ("salesStatus", "SalesStatus", "saleStatus"):
            v = adv.get(key)
            if v is not None and str(v).strip():
                parts.append(str(v))
    return " ".join(parts).lower()


def encar_detail_indicates_sold(detail: Optional[Dict[str, Any]]) -> bool:
    """True, если в JSON явно указано снятие с продажи / продано (не путать с пустым ответом)."""
    if not detail or not isinstance(detail, dict):
        return False
    text = _sales_status_strings(detail)
    if not text.strip():
        return False
    # Encar / UI: 판매완료, contract, sold, …
    markers = (
        "sold",
        "salecomplete",
        "sale_complete",
        "판매완료",
        "판매 완료",
        "계약완료",
        "계약 완료",
        "dealcomplete",
        "deal_complete",
        "closed",
        "removed",
        "delete",
        "종료",
    )
    return any(m in text for m in markers)


def encar_listing_gone_from_api(http_status: int, detail: Optional[Dict[str, Any]]) -> bool:
    """Объявление недоступно для покупки: HTTP gone или JSON говорит «продано»."""
    if http_status in (404, 410):
        return True
    if http_status != 200 or not detail:
        return False
    return encar_detail_indicates_sold(detail)
