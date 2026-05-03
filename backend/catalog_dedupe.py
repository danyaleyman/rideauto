"""Единый ключ дедупликации листинга (блок L): VIN → source:inner_id → id.

Используется в Meilisearch (`catalog_dedupe_key` + `distinctAttribute`) и согласован с логикой
`web/src/lib/catalog-vin-dedupe.ts` (нормализация VIN).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def listing_json_inner_from_cars_data(data: Any) -> Dict[str, Any]:
    """
    Внутренний объект листинга из колонки cars.data (как в sync_meilisearch._listing_json_root).
    """
    raw = data
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    inner = raw.get("data")
    if isinstance(inner, dict) and (
        isinstance(inner.get("pricing_clean"), dict)
        or isinstance(inner.get("identity_clean"), dict)
        or isinstance(inner.get("mark"), str)
        or isinstance(inner.get("pricing_tier"), str)
    ):
        return inner
    return raw


def normalize_vin_for_catalog_dedupe(v: object) -> str:
    s = str(v or "").strip().upper().replace(" ", "").replace("-", "")
    if len(s) < 11:
        return ""
    return s


def _vin_from_listing(data: Dict[str, Any]) -> str:
    for key in ("vin", "VIN", "vehicleIdentificationNumber"):
        raw = data.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


_MAX_DEDUPE_CHAIN = 8


def terminal_car_id_for_dedupe_map(by_car_id: Dict[str, Optional[str]], start: str) -> str:
    """
    По карте car_id → dedupe_canonical_car_id (или None) находит конечный car_id без дальнейшего указателя.
    При цикле или отсутствии ключа возвращает последний валидный узел.
    """
    cur = (start or "").strip()
    if not cur:
        return ""
    seen: set[str] = set()
    for _ in range(_MAX_DEDUPE_CHAIN):
        if cur in seen:
            return cur
        seen.add(cur)
        nxt = by_car_id.get(cur)
        if not nxt or not str(nxt).strip():
            return cur
        cur = str(nxt).strip()
    return cur


def catalog_dedupe_key(car_id: str, source: Optional[str], listing_root: Dict[str, Any]) -> str:
    """
    Стабильный ключ для одного «авто» в выдаче.

    - При валидном VIN (нормализованная длина ≥ 11): ``vin:<VIN>``.
    - Иначе при наличии внутреннего id листинга: ``<source>:<inner>``.
    - Иначе: ``id:<car_id>`` (fallback, дедуп с другими листингами не выполняется).
    """
    cid = str(car_id or "").strip()
    src = (source or "").strip().lower() or "unknown"
    vin = normalize_vin_for_catalog_dedupe(_vin_from_listing(listing_root))
    if vin:
        return f"vin:{vin}"
    inner = (
        str(
            listing_root.get("inner_id")
            or listing_root.get("dongchedi_sku_id")
            or listing_root.get("innerId")
            or "",
        ).strip()
    )
    if inner:
        return f"{src}:{inner}"
    return f"id:{cid}" if cid else "id:unknown"
