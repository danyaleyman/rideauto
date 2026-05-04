from __future__ import annotations

from datetime import datetime, timezone
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


def _shift_ym(ym: int, delta_months: int) -> int:
    year = ym // 100
    month = ym % 100
    ordinal = year * 12 + (month - 1) + delta_months
    return (ordinal // 12) * 100 + (ordinal % 12) + 1


def _parse_year(raw: Optional[str]) -> Optional[int]:
    n = _parse_range_number(raw, as_float=False)
    if n is None:
        return None
    y = int(n)
    if 1900 <= y <= 2100:
        return y
    return None


def _append_year_range_mixed(clauses: List[str], year_from: Optional[str], year_to: Optional[str]) -> None:
    """
    Year range for mixed legacy storage:
      - year as YYYY
      - year as YYYYMM
      - year_month as YYYYMM
      - year_month as ordinal month index (year*12 + month-1)
    """
    y_from = _parse_year(year_from)
    y_to = _parse_year(year_to)
    if y_from is None and y_to is None:
        return

    ym_from = y_from * 100 + 1 if y_from is not None else None
    ym_to = y_to * 100 + 12 if y_to is not None else None
    ord_from = (y_from * 12) if y_from is not None else None
    ord_to = (y_to * 12 + 11) if y_to is not None else None

    parts: List[str] = []
    range_year: List[str] = []
    if y_from is not None:
        range_year.append(f"year >= {y_from}")
    if y_to is not None:
        range_year.append(f"year <= {y_to}")
    if range_year:
        parts.append("(" + " AND ".join(range_year) + ")")

    range_year_ym: List[str] = []
    if ym_from is not None:
        range_year_ym.append(f"year >= {ym_from}")
    if ym_to is not None:
        range_year_ym.append(f"year <= {ym_to}")
    if range_year_ym:
        parts.append("(" + " AND ".join(range_year_ym) + ")")

    range_ym: List[str] = []
    if ym_from is not None:
        range_ym.append(f"year_month >= {ym_from}")
    if ym_to is not None:
        range_ym.append(f"year_month <= {ym_to}")
    if range_ym:
        parts.append("(" + " AND ".join(range_ym) + ")")

    range_ord: List[str] = []
    if ord_from is not None:
        range_ord.append(f"year_month >= {ord_from}")
    if ord_to is not None:
        range_ord.append(f"year_month <= {ord_to}")
    if range_ord:
        parts.append("(" + " AND ".join(range_ord) + ")")

    if parts:
        clauses.append("(" + " OR ".join(parts) + ")")


def build_meilisearch_filter(
    raw_q: Dict[str, str],
    *,
    omit_keys: Optional[FrozenSet[str]] = None,
) -> Optional[str]:
    """
    Строит Meilisearch `filter` по query keys каталога (совместимость с API query-параметрами).

    Не покрыто индексом (пока игнорируется): страховые суммы/кол-во, ДТП, passage_cars.

    Прайсинг Encar (после индексации): ``pricing_tier``, ``customs_included``, алиасы
    ``full_customs_only=1``, ``customs_included`` в ``1``/``true``/``0``/``false``.
    """
    omit = omit_keys or frozenset()
    q = {k: str(v) for k, v in raw_q.items() if k not in omit and v is not None and str(v) != ""}

    clauses: List[str] = []
    include_sold = (raw_q.get("include_sold") or "").strip() == "1"

    src = (q.get("source") or "").strip().lower()
    reg = (q.get("region") or "").strip().lower()
    if src == "encar":
        clauses.append('source = "encar"')
    elif src == "che168":
        clauses.append('source = "che168"')
    elif src == "china" or reg == "china":
        clauses.append('source = "che168"')
    elif reg == "korea":
        clauses.append('source = "encar"')

    if not include_sold:
        clauses.append(
            "("
            "(encar_listing_sold IS NULL OR encar_listing_sold = false) AND "
            "(che168_listing_sold IS NULL OR che168_listing_sold = false)"
            ")"
        )

    inc = _in_clause("brand", expand_filter_values("brand", _csv(q, "marks"), query_flat=q))
    if inc:
        clauses.append(inc)
    inc = _in_clause("model_cluster", expand_filter_values("model_cluster", _csv(q, "clusters"), query_flat=q))
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
    _append_year_range_mixed(clauses, q.get("year_from"), q.get("year_to"))
    _append_range(clauses, "year_month", q.get("ym_from"), q.get("ym_to"), as_float=False)
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

    if q.get("no_accidents_only") == "1":
        clauses.append(
            "("
            "(insurance_cases IS NULL OR insurance_cases = 0) AND "
            "(insurance_payout_krw IS NULL OR insurance_payout_krw = 0) AND "
            "(damaged_parts_count IS NULL OR damaged_parts_count = 0)"
            ")"
        )

    if q.get("new_only") == "1":
        clauses.append("(mileage IS NOT NULL AND mileage <= 500)")

    _valid_pricing_tiers = frozenset({"full_customs", "korea_land_only", "price_on_request"})
    tier_vals = [t for t in _csv(q, "pricing_tier") if t in _valid_pricing_tiers]
    inc_tier = _in_clause("pricing_tier", tier_vals)
    if inc_tier:
        clauses.append(inc_tier)

    if q.get("full_customs_only") == "1":
        clauses.append('pricing_tier = "full_customs"')

    ci_raw = (q.get("customs_included") or "").strip().lower()
    if ci_raw in {"1", "true", "yes", "y", "on"}:
        clauses.append("customs_included = true")
    elif ci_raw in {"0", "false", "no", "off"}:
        clauses.append("customs_included = false")

    if q.get("passable_only") == "1":
        now = datetime.now(timezone.utc)
        ym_5y = (now.year - 5) * 100 + now.month
        ym_3y = (now.year - 3) * 100 + now.month
        y_from = now.year - 5
        y_to = now.year - 3
        ym_from = _shift_ym(ym_5y, +1)
        ym_to = _shift_ym(ym_3y, -1)
        ord_from = (ym_from // 100) * 12 + (ym_from % 100 - 1)
        ord_to = (ym_to // 100) * 12 + (ym_to % 100 - 1)
        # Строгая фильтрация 3–5 лет с учетом того, что в индексе обычно только YYYYMM
        # (без дня): границы месяцев исключаем, чтобы не попадали авто «на 1 день» вне окна.
        # Поддерживаем mixed-форматы хранения:
        # - year_month в YYYYMM
        # - year_month в ordinal month index (year*12 + month-1)
        # - legacy year в YYYYMM
        clauses.append(
            "("
            f"(year_month >= {ym_from} AND year_month <= {ym_to}) OR "
            f"(year_month >= {ord_from} AND year_month <= {ord_to}) OR "
            f"(year >= {ym_from} AND year <= {ym_to}) OR "
            f"(year >= {y_from} AND year <= {y_to})"
            ")"
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
    ("clusters", frozenset({"clusters"}), "model_cluster"),
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

