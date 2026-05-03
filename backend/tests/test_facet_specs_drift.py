"""Блок I: регрессия канона фасетов Meilisearch и связанных контрактов (drift)."""

from __future__ import annotations

from fastapi_app.facet_normalize import FACET_MEILI_ATTR_TO_EN_DOMAIN
from fastapi_app.meilisearch_query import FACET_SPECS_MEILI, meilisearch_sort_list
from fastapi_app.schemas.api import FacetsResponse


def test_facet_specs_meili_dimension_count_stable() -> None:
    assert len(FACET_SPECS_MEILI) == 9


def test_facet_specs_meili_public_keys_stable() -> None:
    assert [spec[0] for spec in FACET_SPECS_MEILI] == [
        "marks",
        "clusters",
        "models",
        "generations",
        "trims",
        "bodies",
        "fuels",
        "transmissions",
        "colors",
    ]


def test_facet_specs_meili_meilisearch_attrs_stable() -> None:
    assert [spec[2] for spec in FACET_SPECS_MEILI] == [
        "brand",
        "model_cluster",
        "model_group",
        "generation",
        "trim",
        "body_type",
        "fuel",
        "transmission",
        "color",
    ]


def test_facet_specs_url_omit_sets_stable() -> None:
    assert [(spec[0], sorted(spec[1])) for spec in FACET_SPECS_MEILI] == [
        ("marks", ["marks"]),
        ("clusters", ["clusters"]),
        ("models", ["models"]),
        ("generations", ["generations"]),
        ("trims", ["trims"]),
        ("bodies", ["body"]),
        ("fuels", ["fuel"]),
        ("transmissions", ["trans"]),
        ("colors", ["color"]),
    ]


def test_facet_meili_attr_en_domain_map_covers_dimensional_attrs() -> None:
    meili_attrs = [spec[2] for spec in FACET_SPECS_MEILI]
    unmapped = frozenset({"body_type", "fuel", "transmission", "color"})
    for attr in meili_attrs:
        if attr in unmapped:
            assert attr not in FACET_MEILI_ATTR_TO_EN_DOMAIN
        else:
            assert attr in FACET_MEILI_ATTR_TO_EN_DOMAIN


def test_facets_response_model_aligns_with_facet_specs() -> None:
    facet_field_names = [name for name in FacetsResponse.model_fields if name != "api_version"]
    assert facet_field_names == [spec[0] for spec in FACET_SPECS_MEILI]


def test_meilisearch_sort_keys_stable() -> None:
    expected = (
        "date_new",
        "date_old",
        "year_new",
        "year_old",
        "price_high",
        "price_low",
        "mileage_high",
        "mileage_low",
    )
    for k in expected:
        sl = meilisearch_sort_list(k)
        assert isinstance(sl, list) and sl, k
    assert meilisearch_sort_list("") == meilisearch_sort_list("date_new")
    assert meilisearch_sort_list("unknown_sort") == meilisearch_sort_list("date_new")
