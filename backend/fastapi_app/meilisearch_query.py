from __future__ import annotations

import json
from typing import Dict, FrozenSet, List, Optional, Sequence

from fastapi_app.facet_normalize import expand_filter_values, merge_facet_distribution_rows


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


def _parse_range_number(raw: Optional[str], *, as_float: bool) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip().replace("\u00a0", " ").replace(",", "").replace("'", "")
    if not s:
        return None
    try:
        if as_float:
            return float(s)
        return float(int(float(s)))
    except ValueError:
        return None


def _append_range(
    clauses: List[str],
    attr: str,
    from_s: Optional[str],
    to_s: Optional[str],
    *,
    as_float: bool,
) -> None:
    v_from = _parse_range_number(from_s, as_float=as_float)
    if v_from is not None:
        clauses.append(f"{attr} >= {v_from}")
    v_to = _parse_range_number(to_s, as_float=as_float)
    if v_to is not None:
        clauses.append(f"{attr} <= {v_to}")


def _parse_year(raw: Optional[str]) -> Optional[int]:
    v = _parse_range_number(raw, as_float=False)
    if v is None:
        return None
    y = int(v)
    if y <= 0:
        return None
    if y >= 190001:
        return y // 100
    return y


def _parse_year_month(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 6:
        try:
            y = int(digits[:4])
            m = int(digits[4:6])
            if y > 0 and 1 <= m <= 12:
                return y * 100 + m
        except ValueError:
            return None
    return None


def _append_year_range(clauses: List[str], year_from_raw: Optional[str], year_to_raw: Optional[str]) -> None:
    year_from = _parse_year(year_from_raw)
    year_to = _parse_year(year_to_raw)
    if year_from is not None:
        # Совместимость с историческим индексом, где у части документов year=YYYYMM.
        clauses.append(f"(year >= {year_from} OR year >= {year_from}00)")
    if year_to is not None:
        # Если year хранится как YYYY, сработает левая часть; если YYYYMM — правая.
        clauses.append(f"(year <= {year_to} OR (year >= 190001 AND year <= {year_to}12))")


def _append_year_month_range(clauses: List[str], q: Dict[str, str]) -> None:
    ym_from = _parse_year_month(q.get("ym_from") or q.get("month_from"))
    ym_to = _parse_year_month(q.get("ym_to") or q.get("month_to"))
    if ym_from is not None:
        clauses.append(f"year_month >= {ym_from}")
    if ym_to is not None:
        clauses.append(f"year_month <= {ym_to}")


def build_meilisearch_filter(
    raw_q: Dict[str, str],
    *,
    omit_keys: Optional[FrozenSet[str]] = None,
) -> Optional[str]:
    """
    Строит Meilisearch `filter` по query keys каталога (совместимость с API query-параметрами).

    Не покрыто индексом (пока игнорируется): страховые суммы/кол-во, ДТП, passage_cars.
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

    inc = _in_clause("brand", expand_filter_values("brand", _csv(q, "marks"), query_flat=q))
    if inc:
        clauses.append(inc)
    inc = _in_clause("model_group", expand_filter_values("model_group", _csv(q, "models"), query_flat=q))
    if inc:
        clauses.append(inc)
    inc = _in_clause("generation", expand_filter_values("generation", _csv(q, "generations"), query_flat=q))
    if inc:
        clauses.append(inc)
    inc = _in_clause("trim", expand_filter_values("trim", _csv(q, "trims"), query_flat=q))
    if inc:
        clauses.append(inc)
    inc = _in_clause("body_type", expand_filter_values("body_type", _csv(q, "body"), query_flat=q))
    if inc:
        clauses.append(inc)
    inc = _in_clause("fuel", expand_filter_values("fuel", _csv(q, "fuel"), query_flat=q))
    if inc:
        clauses.append(inc)
    inc = _in_clause("transmission", expand_filter_values("transmission", _csv(q, "trans"), query_flat=q))
    if inc:
        clauses.append(inc)
    inc = _in_clause("color", expand_filter_values("color", _csv(q, "color"), query_flat=q))
    if inc:
        clauses.append(inc)

    _append_range(clauses, "price", q.get("price_from"), q.get("price_to"), as_float=True)
    _append_range(clauses, "mileage", q.get("mileage_from"), q.get("mileage_to"), as_float=False)
    _append_year_range(clauses, q.get("year_from"), q.get("year_to"))
    _append_year_month_range(clauses, q)
    _append_range(clauses, "power_hp", q.get("power_hp_from"), q.get("power_hp_to"), as_float=False)
    cc_from = _parse_range_number(q.get("engine_cc_from"), as_float=False)
    cc_to = _parse_range_number(q.get("engine_cc_to"), as_float=False)
    if cc_from is not None or cc_to is not None:
        cc_parts: List[str] = []
        if cc_from is not None:
            cc_parts.append(f"displacement_cc >= {cc_from}")
        if cc_to is not None:
            cc_parts.append(f"displacement_cc <= {cc_to}")
        joined = " AND ".join(cc_parts) if cc_parts else "true"
        # Машины без данных по объёму (часто EV/часть гибридов) не выкидываем фильтром.
        clauses.append(f"(displacement_cc IS NULL OR ({joined}))")

    if q.get("power_hp_le_160") == "1":
        clauses.append("power_hp <= 160")

    if q.get("drive_awd") == "1":
        clauses.append(
            '('
            'drive_type = "AWD" OR drive_type = "4WD" OR drive_type = "4x4" OR '
            'drive_type = "Полный" OR drive_type = "Полный привод" OR '
            'drive_type = "全时四驱" OR drive_type = "适时四驱" OR drive_type = "分时四驱"'
            ')'
        )

    if not clauses:
        return None
    return " AND ".join(clauses)


def meilisearch_sort_list(sort_key: str) -> List[str]:
    """Сортировки каталога → Meilisearch sort[]."""
    m: Dict[str, List[str]] = {
        "date_new": ["catalog_created_at:desc", "updated_at:desc"],
        "date_old": ["catalog_created_at:asc", "updated_at:asc"],
        "year_new": ["year:desc", "catalog_created_at:desc", "updated_at:desc"],
        "year_old": ["year:asc", "catalog_created_at:desc", "updated_at:desc"],
        "price_high": ["price:desc"],
        "price_low": ["price:asc"],
        "mileage_high": ["mileage:desc"],
        "mileage_low": ["mileage:asc"],
    }
    return m.get((sort_key or "").strip() or "date_new", m["date_new"])


FACET_SPECS_MEILI = (
    ("marks", frozenset({"marks"}), "brand"),
    ("models", frozenset({"models"}), "model_group"),
    ("generations", frozenset({"generations"}), "generation"),
    ("trims", frozenset({"trims"}), "trim"),
    ("bodies", frozenset({"body"}), "body_type"),
    ("fuels", frozenset({"fuel"}), "fuel"),
    ("transmissions", frozenset({"trans"}), "transmission"),
    ("colors", frozenset({"color"}), "color"),
)


def facet_distribution_to_rows(
    dist: Optional[Dict[str, int]],
    *,
    attr: str = "",
    query_flat: Optional[Dict[str, str]] = None,
) -> List[Dict[str, object]]:
    if not dist:
        return []
    rows = [{"value": k, "count": int(v)} for k, v in dist.items() if k not in ("", None) and int(v) > 0]
    return merge_facet_distribution_rows(attr, rows, query_flat=query_flat)

