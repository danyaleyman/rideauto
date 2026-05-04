from catalog_pg_core import offer_created_at


def test_offer_created_at_from_che168_listing_published():
    p = {"data": {"che168_listing_published_at": "2024-06-15T12:00:00Z"}}
    dt = offer_created_at(p)
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 6
