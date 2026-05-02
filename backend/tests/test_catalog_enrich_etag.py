from __future__ import annotations

from fastapi_app.config import Settings
from fastapi_app.routers.catalog_enrich import CatalogEnrichItem, _catalog_enrich_etag_if_stable


def test_etag_stable_pg_flag_affects_revision():
    settings = Settings(catalog_enrich_etag_revision="t1", catalog_enrich_pg_cache_enabled=True)
    items = [
        CatalogEnrichItem(text="a", domain="color"),
        CatalogEnrichItem(text="b", domain="mark"),
    ]
    e1 = _catalog_enrich_etag_if_stable(items, settings=settings, use_pg_in_request=False, use_llm_in_request=False)
    e2 = _catalog_enrich_etag_if_stable(items, settings=settings, use_pg_in_request=True, use_llm_in_request=False)
    assert e1 is not None and e1.startswith('W/"ce-')
    assert e2 is not None and e1 != e2


def test_etag_disabled_with_llm():
    settings = Settings()
    items = [CatalogEnrichItem(text="a", domain="color")]
    assert (
        _catalog_enrich_etag_if_stable(items, settings=settings, use_pg_in_request=False, use_llm_in_request=True)
        is None
    )
