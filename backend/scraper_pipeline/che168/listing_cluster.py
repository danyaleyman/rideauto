"""Кластеризация связанных лотов Che168 по VIN и близким атрибутам в блоке recommend."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

def _safe_int_lc(v: Any) -> Optional[int]:
    try:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            s = v.strip().replace("\u00a0", " ").replace(" ", "").replace(",", "").split(".")[0]
            if not s:
                return None
            return int(float(s))
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _safe_float_lc(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(str(v).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def _norm_label(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def che168_recommend_raw_items(recommend: Any, *, limit: int = 40) -> List[dict]:
    """Сырые элементы carlist из /recommend (полные dict)."""
    if not isinstance(recommend, dict):
        return []
    layer = recommend.get("result") if isinstance(recommend.get("result"), dict) else recommend
    if not isinstance(layer, dict):
        return []
    for key in ("carlist", "carList", "list", "rows"):
        v = layer.get(key)
        if isinstance(v, list):
            items = [x for x in v if isinstance(x, dict)]
            return items[:limit]
    return []


def _listing_id_from_item(it: dict) -> str:
    for k in ("id", "infoid", "infoId", "InfoId"):
        v = it.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _vin_from_item(it: dict) -> Optional[str]:
    for k in ("vin", "VIN", "frameno", "frameNo"):
        v = it.get(k)
        if v is not None and str(v).strip():
            return str(v).strip().upper()
    return None


def _facets_from_recommend_item(it: dict) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[float], Optional[int]]:
    mark = (
        it.get("brandname")
        or it.get("brandName")
        or it.get("BrandName")
        or it.get("mark")
    )
    model = (
        it.get("seriesname")
        or it.get("seriesName")
        or it.get("modelname")
        or it.get("modelName")
        or it.get("vehicleName")
    )
    year = _safe_int_lc(it.get("year"))
    price = _safe_float_lc(it.get("price"))
    km = _safe_int_lc(it.get("mileage") or it.get("mileagekm") or it.get("mileageKm"))
    if km is not None and km < 0:
        km = None
    m = str(mark).strip() if mark else None
    mo = str(model).strip() if model else None
    return m or None, mo or None, year, price, km


CLUSTER_CALIBRATION_PRESETS: Dict[str, Tuple[float, int, int]] = {
    "strict": (0.05, 15_000, 1),
    "balanced": (0.08, 25_000, 1),
    "loose": (0.12, 40_000, 2),
}


def resolve_cluster_calibration(lc: Dict[str, Any]) -> Dict[str, Any]:
    """Профиль strict|balanced|loose + явные поля перекрывают preset."""
    profile = str(lc.get("calibration_profile") or "balanced").strip().lower()
    ptol, ktol, ydiff = CLUSTER_CALIBRATION_PRESETS.get(
        profile,
        CLUSTER_CALIBRATION_PRESETS["balanced"],
    )
    return {
        "price_rel_tol": float(lc.get("price_rel_tol", ptol)),
        "km_abs_tol": int(lc.get("km_abs_tol", ktol)),
        "year_max_diff": int(lc.get("year_max_diff", ydiff)),
        "near_miss_price_rel_cap": float(lc.get("near_miss_price_rel_cap", 0.15)),
        "near_miss_km_abs_cap": int(lc.get("near_miss_km_abs_cap", 45_000)),
    }


def cluster_che168_similar_listings(
    center_id: str,
    *,
    vin: Optional[str],
    mark: Optional[str],
    model: Optional[str],
    year: Optional[int],
    price_cny: Optional[float],
    km: Optional[int],
    recommend_items: List[dict],
    price_rel_tol: float = 0.08,
    km_abs_tol: int = 25_000,
    year_max_diff: int = 1,
    near_miss_price_rel_cap: float = 0.15,
    near_miss_km_abs_cap: int = 45_000,
    telemetry: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """
    Возвращает peer_ids (без center_id), cluster_id, method ∈ {vin, attribute, none}.
    Без общего VIN в ответе — группа по (mark, model, год±1, цена ±tol, пробег ±tol).
    """
    cid = str(center_id).strip()
    peers: List[str] = []
    method = "none"

    items = [it for it in recommend_items if isinstance(it, dict)]
    if vin and len(vin) >= 8:
        for it in items:
            oid = _listing_id_from_item(it)
            if not oid or oid == cid:
                continue
            v2 = _vin_from_item(it)
            if v2 and v2 == vin.upper():
                peers.append(oid)
        if peers:
            method = "vin"
            digest = hashlib.sha1(f"vin:{vin.upper()}".encode("utf-8")).hexdigest()[:20]
            return {
                "peer_ids": _dedupe_keep_order(peers),
                "cluster_id": f"che168:vin:{digest}",
                "method": method,
                "cluster_size": len(peers) + 1,
            }

    nm = _norm_label(mark)
    nmo = _norm_label(model)
    if nm and nmo and year is not None and price_cny and price_cny > 0:
        for it in items:
            oid = _listing_id_from_item(it)
            if not oid or oid == cid:
                continue
            om, omo, oy, op, okm = _facets_from_recommend_item(it)
            if _norm_label(om) != nm or _norm_label(omo) != nmo:
                continue
            if oy is None or abs(int(oy) - int(year)) > year_max_diff:
                continue
            if op is None or op <= 0:
                continue
            rel = abs(float(price_cny) - float(op)) / max(float(price_cny), float(op), 1.0)
            if rel > price_rel_tol:
                if (
                    telemetry is not None
                    and near_miss_price_rel_cap > price_rel_tol
                    and rel <= near_miss_price_rel_cap
                ):
                    telemetry["cluster_near_miss_price"] = telemetry.get("cluster_near_miss_price", 0) + 1
                continue
            if km is not None and okm is not None:
                gap_km = abs(int(km) - int(okm))
                if gap_km > km_abs_tol:
                    if (
                        telemetry is not None
                        and near_miss_km_abs_cap > km_abs_tol
                        and gap_km <= near_miss_km_abs_cap
                    ):
                        telemetry["cluster_near_miss_km"] = telemetry.get("cluster_near_miss_km", 0) + 1
                    continue
            peers.append(oid)

    if peers:
        method = "attribute"
        sig = "|".join(sorted({cid, *peers}))
        digest = hashlib.sha1(sig.encode("utf-8")).hexdigest()[:20]
        return {
            "peer_ids": _dedupe_keep_order(peers),
            "cluster_id": f"che168:attr:{digest}",
            "method": method,
            "cluster_size": len(peers) + 1,
        }

    return {"peer_ids": [], "cluster_id": None, "method": method, "cluster_size": 1}


def _dedupe_keep_order(ids: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in ids:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out
