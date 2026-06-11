"""Агрегация типичных цен по когорте «похожих» объявлений (Postgres)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import asyncpg

from catalog_pg_core import normalize_calendar_year_value
from fastapi_app.facet_normalize import expand_filter_values
from fastapi_app.meilisearch_query import (
    _append_year_range_mixed,
    _csv,
    _parse_range_number,
    _parse_year,
    _passable_age_bounds,
)

MIN_COHORT_N = 8
LISTING_YEAR_DELTA = 1
LISTING_MILEAGE_RATIO = 0.25

# Query keys, не влияющие на когорту сравнения.
_BENCHMARK_OMIT_KEYS = frozenset(
    {
        "q",
        "query",
        "page",
        "per_page",
        "limit",
        "cursor",
        "sort",
        "full",
        "price_from",
        "price_to",
        "car_id",
        "scope",
    }
)


@dataclass(frozen=True)
class SqlWhere:
    sql: str
    params: Tuple[Any, ...]


def catalog_benchmark_eligible(flat: Dict[str, str]) -> bool:
    marks = _csv(flat, "marks")
    models = _csv(flat, "models")
    clusters = _csv(flat, "clusters")
    return bool(marks) and bool(models or clusters)


def _flat_for_benchmark(raw: Dict[str, str]) -> Dict[str, str]:
    return {k: str(v) for k, v in raw.items() if k not in _BENCHMARK_OMIT_KEYS and v is not None and str(v) != ""}


def _append_sql_in(
    parts: List[str],
    params: List[Any],
    column: str,
    values: Sequence[str],
) -> None:
    if not values:
        return
    placeholders = ", ".join(f"${i}" for i in range(len(params) + 1, len(params) + len(values) + 1))
    parts.append(f"{column} IN ({placeholders})")
    params.extend(values)


def _append_sql_or_group(
    parts: List[str],
    params: List[Any],
    clauses: List[str],
) -> None:
    if not clauses:
        return
    if len(clauses) == 1:
        parts.append(clauses[0])
    else:
        parts.append("(" + " OR ".join(clauses) + ")")


def _append_year_range_sql(parts: List[str], year_from: Optional[str], year_to: Optional[str]) -> None:
    """Год/месяц: те же правила, что Meilisearch (литералы в SQL — без параметров)."""
    clauses: List[str] = []
    _append_year_range_mixed(clauses, year_from, year_to)
    if clauses:
        meili = " AND ".join(clauses)
        pg = (
            meili.replace("year_month >=", "cars.year_month >=")
            .replace("year_month <=", "cars.year_month <=")
            .replace("year >=", "cars.year >=")
            .replace("year <=", "cars.year <=")
        )
        parts.append(f"({pg})")


def _listing_year_bounds(car_year: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
    if car_year is None:
        return None, None
    yf = max(1900, car_year - LISTING_YEAR_DELTA)
    yt = min(2100, car_year + LISTING_YEAR_DELTA)
    return str(yf), str(yt)


def _car_calendar_year(row: asyncpg.Record) -> Optional[int]:
    y = row.get("year")
    if y is not None:
        try:
            cy = normalize_calendar_year_value(int(y))
            if cy is not None:
                return cy
        except (TypeError, ValueError):
            pass
    ym = row.get("year_month")
    if ym is not None:
        try:
            iym = int(ym)
            if 190_001 <= iym <= 210_012:
                return iym // 100
        except (TypeError, ValueError):
            pass
    return None


def build_benchmark_sql_where(
    flat: Dict[str, str],
    *,
    listing_row: Optional[asyncpg.Record] = None,
) -> SqlWhere:
    q = _flat_for_benchmark(flat)
    parts: List[str] = [
        "(cars.encar_listing_sold IS NOT TRUE)",
        "(cars.che168_listing_sold IS NOT TRUE)",
        "cars.price_rub IS NOT NULL",
        "cars.price_rub > 0",
    ]
    params: List[Any] = []

    src = (q.get("source") or "").strip().lower()
    reg = (q.get("region") or "").strip().lower()
    if src == "encar" or reg == "korea":
        parts.append("cars.source = 'encar'")
    elif src in {"che168", "china"} or reg == "china":
        parts.append("cars.source = 'che168'")
    elif listing_row is not None:
        ls = str(listing_row.get("source") or "").strip()
        if ls:
            parts.append(f"cars.source = ${len(params) + 1}")
            params.append(ls)

    marks = expand_filter_values("brand", _csv(q, "marks"), query_flat=q)
    models = expand_filter_values("model_group", _csv(q, "models"), query_flat=q)
    clusters = expand_filter_values("model_cluster", _csv(q, "clusters"), query_flat=q)
    model_vals = list(dict.fromkeys([*models, *clusters]))

    if listing_row is not None:
        lm = str(listing_row.get("mark") or "").strip()
        if lm and not marks:
            marks = [lm]
        lmodel = str(listing_row.get("model") or "").strip()
        lgroup = str(listing_row.get("encar_model_group") or "").strip()
        if not model_vals:
            if lmodel:
                model_vals.append(lmodel)
            if lgroup and lgroup not in model_vals:
                model_vals.append(lgroup)

    if marks:
        _append_sql_in(parts, params, "cars.mark", marks)

    model_clauses: List[str] = []
    if model_vals:
        _append_sql_in(model_clauses, params, "cars.model", model_vals)
        _append_sql_in(model_clauses, params, "cars.encar_model_group", model_vals)
    _append_sql_or_group(parts, params, model_clauses)

    gens = expand_filter_values("generation", _csv(q, "generations"), query_flat=q)
    if gens:
        _append_sql_in(parts, params, "cars.generation", gens)
    trims = expand_filter_values("trim", _csv(q, "trims"), query_flat=q)
    if trims:
        _append_sql_in(parts, params, "cars.trim_name", trims)

    for key, col, expand_attr in (
        ("body", "cars.body_type", "body_type"),
        ("fuel", "cars.fuel_type", "fuel"),
        ("trans", "cars.transmission_type", "transmission"),
        ("color", "cars.color", "color"),
    ):
        vals = expand_filter_values(expand_attr, _csv(q, key), query_flat=q)
        if vals:
            _append_sql_in(parts, params, col, vals)

    y_from = q.get("year_from")
    y_to = q.get("year_to")
    if listing_row is not None:
        cy = _car_calendar_year(listing_row)
        ly_from, ly_to = _listing_year_bounds(cy)
        if ly_from is not None:
            y_from, y_to = ly_from, ly_to
    _append_year_range_sql(parts, y_from, y_to)

    m_from = _parse_range_number(q.get("mileage_from"), as_float=False)
    m_to = _parse_range_number(q.get("mileage_to"), as_float=False)
    if listing_row is not None and m_from is None and m_to is None:
        mk = listing_row.get("mileage_km")
        if mk is not None:
            try:
                m = int(mk)
                if m > 0:
                    delta = max(1, int(m * LISTING_MILEAGE_RATIO))
                    parts.append(f"cars.mileage_km >= ${len(params) + 1}")
                    params.append(max(0, m - delta))
                    parts.append(f"cars.mileage_km <= ${len(params) + 1}")
                    params.append(m + delta)
            except (TypeError, ValueError):
                pass
    else:
        if m_from is not None:
            parts.append(f"cars.mileage_km >= ${len(params) + 1}")
            params.append(int(m_from))
        if m_to is not None:
            parts.append(f"cars.mileage_km <= ${len(params) + 1}")
            params.append(int(m_to))

    p_from = _parse_range_number(q.get("power_hp_from"), as_float=False)
    p_to = _parse_range_number(q.get("power_hp_to"), as_float=False)
    if p_from is not None:
        parts.append(f"cars.power_hp >= ${len(params) + 1}")
        params.append(int(p_from))
    if p_to is not None:
        parts.append(f"cars.power_hp <= ${len(params) + 1}")
        params.append(int(p_to))

    cc_from = _parse_range_number(q.get("engine_cc_from"), as_float=False)
    cc_to = _parse_range_number(q.get("engine_cc_to"), as_float=False)
    if cc_from is not None or cc_to is not None:
        cc_parts: List[str] = ["cars.displacement_cc IS NULL"]
        inner: List[str] = []
        if cc_from is not None:
            inner.append(f"cars.displacement_cc >= ${len(params) + 1}")
            params.append(int(cc_from))
        if cc_to is not None:
            inner.append(f"cars.displacement_cc <= ${len(params) + 1}")
            params.append(int(cc_to))
        if inner:
            cc_parts.append("(" + " AND ".join(inner) + ")")
        parts.append("(" + " OR ".join(cc_parts) + ")")

    if q.get("power_hp_le_160") == "1":
        parts.append("cars.power_hp <= 160")

    if q.get("drive_awd") == "1":
        parts.append(
            "cars.drive_type IN ('AWD', '4WD', '4x4', 'Полный', 'Полный привод', "
            "'全时四驱', '适时四驱', '分时四驱')"
        )

    if q.get("new_only") == "1":
        parts.append("cars.mileage_km IS NOT NULL AND cars.mileage_km <= 500")

    if q.get("passable_only") == "1":
        now = datetime.now(timezone.utc)
        ym_from, ym_to, ord_from, ord_to = _passable_age_bounds(now)
        parts.append(
            f"((cars.year_month >= {ym_from} AND cars.year_month <= {ym_to}) OR "
            f"(cars.year_month >= {ord_from} AND cars.year_month <= {ord_to}))"
        )

    return SqlWhere(sql=" AND ".join(parts), params=tuple(params))


def _append_clean_condition(parts: List[str]) -> None:
    parts.append("cars.insurance_cases = 0")
    parts.append("COALESCE(cars.insurance_payout_krw, 0) = 0")
    parts.append("cars.damaged_parts_count = 0")


async def fetch_price_aggregate(pool: asyncpg.Pool, where: SqlWhere, *, clean: bool = False) -> Optional[Dict[str, Any]]:
    parts = [where.sql]
    if clean:
        _append_clean_condition(parts)
    sql = f"""
        SELECT
          COUNT(*)::int AS n,
          percentile_cont(0.25) WITHIN GROUP (ORDER BY cars.price_rub) AS p25_rub,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY cars.price_rub) AS median_rub,
          percentile_cont(0.75) WITHIN GROUP (ORDER BY cars.price_rub) AS p75_rub
        FROM cars
        WHERE {" AND ".join(parts)}
    """
    row = await pool.fetchrow(sql, *where.params)
    if not row or not row["n"] or int(row["n"]) < MIN_COHORT_N:
        return None
    return {
        "n": int(row["n"]),
        "p25_rub": _round_rub(row["p25_rub"]),
        "median_rub": _round_rub(row["median_rub"]),
        "p75_rub": _round_rub(row["p75_rub"]),
    }


def _round_rub(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def classify_price_band(price_rub: float, p25: int, p75: int) -> str:
    if price_rub < p25:
        return "below_typical"
    if price_rub > p75:
        return "above_typical"
    return "typical"


def vs_median_percent(price_rub: float, median_rub: int) -> Optional[int]:
    if not median_rub or median_rub <= 0:
        return None
    return int(round((price_rub - median_rub) / median_rub * 100))


def build_cohort_meta(
    flat: Dict[str, str],
    *,
    listing_row: Optional[asyncpg.Record] = None,
) -> Dict[str, Any]:
    q = _flat_for_benchmark(flat)
    src = (q.get("source") or "").strip().lower()
    reg = (q.get("region") or "").strip().lower()
    market = "china" if src in {"che168", "china"} or reg == "china" else "korea"
    if listing_row is not None:
        ls = str(listing_row.get("source") or "")
        if ls == "che168":
            market = "china"
        elif ls == "encar":
            market = "korea"

    marks = _csv(q, "marks") or (
        [str(listing_row.get("mark")).strip()]
        if listing_row and listing_row.get("mark")
        else []
    )
    models = _csv(q, "models")
    clusters = _csv(q, "clusters")
    year_from = q.get("year_from")
    year_to = q.get("year_to")
    mileage_note: Optional[str] = None
    if listing_row is not None:
        cy = _car_calendar_year(listing_row)
        yf, yt = _listing_year_bounds(cy)
        if yf is not None:
            year_from, year_to = yf, yt
        mk = listing_row.get("mileage_km")
        if mk is not None:
            try:
                m = int(mk)
                if m > 0:
                    mileage_note = f"±{int(LISTING_MILEAGE_RATIO * 100)}%"
            except (TypeError, ValueError):
                pass

    return {
        "market": market,
        "brand": marks[0] if len(marks) == 1 else None,
        "brands": marks,
        "models": models,
        "clusters": clusters,
        "year_from": int(year_from) if year_from and str(year_from).isdigit() else _parse_year(year_from),
        "year_to": int(year_to) if year_to and str(year_to).isdigit() else _parse_year(year_to),
        "mileage_band": mileage_note,
    }


async def compute_price_benchmark(
    pool: asyncpg.Pool,
    flat: Dict[str, str],
    *,
    listing_row: Optional[asyncpg.Record] = None,
    listing_price_rub: Optional[float] = None,
) -> Dict[str, Any]:
    where = build_benchmark_sql_where(flat, listing_row=listing_row)
    peer_all = await fetch_price_aggregate(pool, where, clean=False)
    market = build_cohort_meta(flat, listing_row=listing_row).get("market")
    peer_clean = None
    if market == "korea":
        peer_clean = await fetch_price_aggregate(pool, where, clean=True)

    listing_block: Optional[Dict[str, Any]] = None
    if listing_price_rub is not None and peer_all:
        med = peer_all.get("median_rub")
        p25 = peer_all.get("p25_rub")
        p75 = peer_all.get("p75_rub")
        if med is not None and p25 is not None and p75 is not None:
            listing_block = {
                "price_rub": int(round(listing_price_rub)),
                "vs_median_all_pct": vs_median_percent(listing_price_rub, med),
                "band": classify_price_band(listing_price_rub, p25, p75),
            }
            if peer_clean and peer_clean.get("median_rub"):
                listing_block["vs_median_clean_pct"] = vs_median_percent(
                    listing_price_rub, int(peer_clean["median_rub"])
                )

    return {
        "cohort": build_cohort_meta(flat, listing_row=listing_row),
        "peer_all": peer_all,
        "peer_clean": peer_clean,
        "listing": listing_block,
        "min_n": MIN_COHORT_N,
    }
