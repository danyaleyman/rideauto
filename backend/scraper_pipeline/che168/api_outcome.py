"""Классификация ответов Che168 Global: ok / gone / retry (устойчивость воркера)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional, Tuple

Outcome = Literal["ok", "gone", "retry"]

SESSION_HINTS = re.compile(
    r"session|登录|登錄|login|unauthorized|未授权|未授權|token|device|cookie|请先|請先|expire|过期|過期",
    re.I,
)
RETRY_HINTS = re.compile(
    r"繁忙|稍后|稍後|timeout|try\s*again|rate|频繁|頻繁|too\s+many|503|502|gateway",
    re.I,
)
GONE_HINTS = re.compile(
    r"下架|售出|不存在|已售|无效|無效|删除|刪除|not\s*found|sold|off\s*shelf|removed|no\s+data",
    re.I,
)


def che168_returncode_meta(d: Any) -> Tuple[Optional[int], str]:
    if not isinstance(d, dict):
        return None, ""
    msg = str(d.get("message") or d.get("msg") or d.get("Message") or "").strip()
    for k in ("returncode", "returnCode", "code", "status"):
        v = d.get(k)
        if v is None or v == "":
            continue
        try:
            return int(v), msg
        except (TypeError, ValueError):
            continue
    return None, msg


def _unwrap_top(d: dict) -> dict:
    for k in ("result", "data", "carinfo"):
        v = d.get(k)
        if isinstance(v, dict) and len(v) >= 2:
            return v
    return d


def che168_body_has_listing_signals(body: dict) -> bool:
    if not body:
        return False
    for k in (
        "id",
        "infoid",
        "infoId",
        "title",
        "price",
        "brandname",
        "brandName",
        "vin",
        "VIN",
        "specid",
        "specId",
    ):
        v = body.get(k)
        if v is not None and str(v).strip():
            return True
    return False


def che168_response_suggests_session_refresh(raw: Any) -> bool:
    """Бизнес-ответ API с намёком на сессию/куки/device — имеет смысл перезапустить Playwright bootstrap."""
    if not isinstance(raw, dict):
        return False
    rc, msg = che168_returncode_meta(raw)
    if rc is None or rc == 0:
        return False
    text = f"{msg} {raw.get('description', '')}"
    return bool(SESSION_HINTS.search(text))


def che168_carinfo_outcome(
    http_status: int,
    raw: Any,
) -> Outcome:
    if http_status in (404, 410):
        return "gone"
    if http_status != 200 or raw is None:
        return "retry"
    if not isinstance(raw, dict):
        return "retry"

    rc, msg = che168_returncode_meta(raw)
    text = f"{msg} {raw.get('description', '')}"
    if rc is not None and rc != 0:
        if SESSION_HINTS.search(text):
            return "retry"
        if RETRY_HINTS.search(text):
            return "retry"
        if GONE_HINTS.search(text):
            return "gone"
        # Типичный случай: бизнес-код «лота нет» без явного текста — считаем снятым.
        return "gone"

    body = _unwrap_top(raw)
    if not che168_body_has_listing_signals(body):
        return "gone"
    return "ok"


def che168_search_pagecount(layer: dict) -> Optional[int]:
    if not isinstance(layer, dict):
        return None
    for k in ("pagecount", "pageCount", "totalpage", "totalPage", "page_total"):
        v = layer.get(k)
        if v is not None and str(v).strip().isdigit():
            n = int(str(v).strip())
            return n if n > 0 else None
    return None


def che168_extract_similar_ids(recommend: Any, *, limit: int = 30) -> List[str]:
    if not isinstance(recommend, dict):
        return []
    layer = recommend.get("result") if isinstance(recommend.get("result"), dict) else recommend
    if not isinstance(layer, dict):
        return []
    items: List[dict] = []
    for key in ("carlist", "carList", "list", "rows"):
        v = layer.get(key)
        if isinstance(v, list):
            items = [x for x in v if isinstance(x, dict)]
            break
    out: List[str] = []
    seen: set[str] = set()
    for it in items:
        for k in ("id", "infoid", "infoId"):
            v = it.get(k)
            if v is not None and str(v).strip():
                s = str(v).strip()
                if s not in seen:
                    seen.add(s)
                    out.append(s)
                break
        if len(out) >= limit:
            break
    return out


def che168_flatten_dealer(report: Any) -> Dict[str, Any]:
    """Плоские поля продавца для seller_clean / data (PII может быть — redact в saver)."""
    if not isinstance(report, dict):
        return {}
    layer = report.get("result") if isinstance(report.get("result"), dict) else report
    if not isinstance(layer, dict):
        return {}

    def pick(*keys: str) -> Optional[str]:
        for k in keys:
            v = layer.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return None

    out: Dict[str, Any] = {}
    name = pick("dealername", "dealerName", "name", "shopname", "shopName", "companyname")
    if name:
        out["dealer_name"] = name
    did = pick("dealerid", "dealerId", "id")
    if did:
        out["dealer_id"] = did
    addr = pick("address", "addressDetail", "shopaddress")
    if addr:
        out["dealer_address"] = addr
    rating = layer.get("score") or layer.get("rating") or layer.get("dealerstar")
    if rating is not None and str(rating).strip():
        out["dealer_rating"] = rating
    return out
