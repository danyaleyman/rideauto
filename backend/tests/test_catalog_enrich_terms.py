from __future__ import annotations

from fastapi_app.catalog_term_enrichment import enrich_one


def test_enrich_fuel_ko_gasoline():
    row = enrich_one("가솔린", "fuel")
    assert row["ru"] == "Бензин"
    assert row["source_ru"] == "fuel_facet"


def test_enrich_trim_domain_no_crash():
    row = enrich_one("some trim", "trim_name")
    assert "text_in" in row
