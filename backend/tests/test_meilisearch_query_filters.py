from fastapi_app.meilisearch_query import build_meilisearch_filter


def test_search_filter_excludes_sold_by_default():
    q = {"region": "korea", "source": "encar"}
    filt = build_meilisearch_filter(q)
    assert filt is not None
    assert "encar_listing_sold" in filt
    assert "dongchedi_listing_sold" in filt
    assert " = false" in filt


def test_search_filter_can_include_sold_on_flag():
    q = {"region": "korea", "source": "encar", "include_sold": "1"}
    filt = build_meilisearch_filter(q)
    assert filt is not None
    assert "encar_listing_sold" not in filt
    assert "dongchedi_listing_sold" not in filt
