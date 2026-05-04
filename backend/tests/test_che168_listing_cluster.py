from scraper_pipeline.che168.listing_cluster import (
    che168_recommend_raw_items,
    cluster_che168_similar_listings,
)


def test_cluster_by_vin_in_recommend_items():
    items = [
        {"infoid": "2", "vin": "WBAZZZ999"},
        {"infoid": "3", "vin": "OTHER"},
    ]
    r = cluster_che168_similar_listings(
        "1",
        vin="WBAZZZ999",
        mark="BMW",
        model="X5",
        year=2020,
        price_cny=500_000.0,
        km=40_000,
        recommend_items=items,
    )
    assert r["method"] == "vin"
    assert r["peer_ids"] == ["2"]
    assert r["cluster_id"].startswith("che168:vin:")


def test_cluster_by_attribute_proximity():
    items = [
        {
            "infoid": "11",
            "brandname": "BMW",
            "modelname": "X5",
            "year": 2020,
            "price": 502_000,
            "mileage": 41_000,
        }
    ]
    r = cluster_che168_similar_listings(
        "10",
        vin=None,
        mark="BMW",
        model="X5",
        year=2020,
        price_cny=500_000.0,
        km=40_000,
        recommend_items=items,
    )
    assert r["method"] == "attribute"
    assert "11" in r["peer_ids"]


def test_recommend_raw_items():
    raw = {"result": {"carlist": [{"id": 1, "price": 1}, {"id": 2}]}}
    assert len(che168_recommend_raw_items(raw, limit=10)) == 2
