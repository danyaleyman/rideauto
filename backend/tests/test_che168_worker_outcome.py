from scraper_pipeline.che168.api_outcome import che168_body_has_listing_signals


def test_body_signals():
    assert che168_body_has_listing_signals({"id": 1, "title": "x"}) is True
    assert che168_body_has_listing_signals({}) is False
