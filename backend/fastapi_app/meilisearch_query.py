from __future__ import annotations

import json
from typing import Dict, FrozenSet, List, Optional, Sequence


def _csv(q: Dict[str, str], key: str) -> List[str]:
    raw = q.get(key)
    if raw is None or raw == "":
        return []
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def _in_clause(attr: str, values: Sequence[str]) -> Optional[str]:
    if not values:
        return None
    inner = ", ".join(json.dumps(v, ensure_ascii=False) for v in values)
    return f"{attr} IN [{inner}]"


def _append_range(
    clauses: List[str],
    attr: str,
    from_s: Optional[str],
    to_s: Optional[str],
    *,
    as_float: bool,
) -> None:
    if from_s:
        try:
            v = float(from_s) if as_float else int(from_s)
            clauses.append(f"{attr} >= {v}")
        except ValueError:
            pass
    if to_s:
        try:
            v = float(to_s) if as_float else int(to_s)
            clauses.append(f"{attr} <= {v}")
        except ValueError:
            pass


def build_meilisearch_filter(
    raw_q: Dict[str, str],
    *,
    omit_keys: Optional[FrozenSet[str]] = None,
) -> Optional[str]:
    """
    Строит Meilisearch `filter` по query keys каталога (совместимость с API query-параметрами).

    Не покрыто индексом (пока игнорируется): страховые суммы/кол-во, ДТП, passage_cars,
    объём двигателя / мощность — после добавления полей в Meilisearch расширить sync + settings.
    """
    omit = omit_keys or frozenset()
    q = {k: str(v) for k, v in raw_q.items() if k not in omit and v is not None and str(v) != ""}

    clauses: List[str] = []

    src = (q.get("source") or "").strip().lower()
    reg = (q.get("region") or "").strip().lower()
    if src == "encar":
        clauses.append('source = "encar"')
    elif src == "dongchedi":
        clauses.append('source = "dongchedi"')
    elif src == "che168":
        clauses.append("year_month = -1")
    elif src == "china" or reg == "china":
        clauses.append('source = "dongchedi"')
    elif reg == "korea":
        clauses.append('source = "encar"')

    inc = _in_clause("brand", _csv(q, "marks"))
    if inc:
        clauses.append(inc)
    inc = _in_clause("model", _csv(q, "models"))
    if inc:
        clauses.append(inc)
    inc = _in_clause("generation", _csv(q, "generations"))
    if inc:
        clauses.append(inc)
    inc = _in_clause("trim", _csv(q, "trims"))
    if inc:
        clauses.append(inc)
    inc = _in_clause("body_type", _csv(q, "body"))
    if inc:
        clauses.append(inc)
    inc = _in_clause("fuel", _csv(q, "fuel"))
    if inc:
        clauses.append(inc)
    inc = _in_clause("transmission", _csv(q, "trans"))
    if inc:
        clauses.append(inc)
    inc = _in_clause("color", _csv(q, "color"))
    if inc:
        clauses.append(inc)

    _append_range(clauses, "price", q.get("price_from"), q.get("price_to"), as_float=True)
    _append_range(clauses, "mileage", q.get("mileage_from"), q.get("mileage_to"), as_float=False)
    _append_range(clauses, "year", q.get("year_from"), q.get("year_to"), as_float=False)
    _append_range(clauses, "year_month", q.get("ym_from"), q.get("ym_to"), as_float=False)

    if q.get("drive_awd") == "1":
        clauses.append('drive_type = "AWD"')

    if not clauses:
        return None
    return " AND ".join(clauses)


def meilisearch_sort_list(sort_key: str) -> List[str]:
    """Сортировки каталога → Meilisearch sort[]."""
    m: Dict[str, List[str]] = {
        "date_new": ["updated_at:desc"],
        "date_old": ["updated_at:asc"],
        "year_new": ["year:desc", "updated_at:desc"],
        "year_old": ["year:asc", "updated_at:desc"],
        "price_high": ["price:desc"],
        "price_low": ["price:asc"],
        "mileage_high": ["mileage:desc"],
        "mileage_low": ["mileage:asc"],
    }
    return m.get((sort_key or "").strip() or "date_new", m["date_new"])


FACET_SPECS_MEILI = (
    ("marks", frozenset({"marks"}), "brand"),
    ("models", frozenset({"models"}), "model"),
    ("generations", frozenset({"generations"}), "generation"),
    ("trims", frozenset({"trims"}), "trim"),
    ("bodies", frozenset({"body"}), "body_type"),
    ("fuels", frozenset({"fuel"}), "fuel"),
    ("transmissions", frozenset({"trans"}), "transmission"),
    ("colors", frozenset({"color"}), "color"),
)


def facet_distribution_to_rows(dist: Optional[Dict[str, int]]) -> List[Dict[str, object]]:
    if not dist:
        return []
    rows = [{"value": k, "count": int(v)} for k, v in dist.items() if k not in ("", None)]
    rows.sort(key=lambda r: str(r["value"]).lower())
    return rows

