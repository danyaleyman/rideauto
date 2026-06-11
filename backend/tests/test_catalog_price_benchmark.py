from __future__ import annotations

from fastapi_app.catalog_price_benchmark import (
    MIN_COHORT_N,
    build_benchmark_sql_where,
    catalog_benchmark_eligible,
    classify_price_band,
    vs_median_percent,
)


def test_catalog_benchmark_eligible_requires_mark_and_model() -> None:
    assert not catalog_benchmark_eligible({})
    assert not catalog_benchmark_eligible({"marks": "Hyundai"})
    assert catalog_benchmark_eligible({"marks": "Hyundai", "models": "Sonata"})
    assert catalog_benchmark_eligible({"marks": "Hyundai", "clusters": "Sonata"})


def test_classify_price_band() -> None:
    assert classify_price_band(1_000_000, 2_000_000, 3_000_000) == "below_typical"
    assert classify_price_band(2_500_000, 2_000_000, 3_000_000) == "typical"
    assert classify_price_band(3_500_000, 2_000_000, 3_000_000) == "above_typical"


def test_vs_median_percent() -> None:
    assert vs_median_percent(2_400_000, 2_000_000) == 20
    assert vs_median_percent(1_600_000, 2_000_000) == -20


def test_build_benchmark_sql_where_korea_mark_model() -> None:
    where = build_benchmark_sql_where(
        {"region": "korea", "marks": "Hyundai", "models": "Sonata"},
    )
    assert "cars.source = 'encar'" in where.sql
    assert "cars.mark IN" in where.sql
    assert "cars.model IN" in where.sql or "cars.encar_model_group IN" in where.sql
    assert "price_rub > 0" in where.sql


def test_min_cohort_n_constant() -> None:
    assert MIN_COHORT_N == 8
