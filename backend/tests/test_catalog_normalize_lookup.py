from __future__ import annotations

from fastapi_app.catalog_term_enrichment import (
    compact_catalog_lookup_variant,
    enrich_one,
    normalize_catalog_lookup_key,
)


def test_normalize_fullwidth_spaces():
    assert normalize_catalog_lookup_key("\u3000 A  B\u3000") == "A B"


def test_compact_static_variant():
    assert compact_catalog_lookup_variant(" AB - cd ") == "ABcd"


def test_enrich_fuel_uses_normalized_key():
    row = enrich_one("\u3000가솔린\u3000", "fuel")
    assert row["ru"] == "Бензин"
    assert row["text_in"] == "\u3000가솔린\u3000".strip()
