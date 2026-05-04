from catalog_dedupe import (
    catalog_dedupe_key,
    listing_json_inner_from_cars_data,
    normalize_vin_for_catalog_dedupe,
)


def test_normalize_vin_strips_and_min_length():
    assert normalize_vin_for_catalog_dedupe(" ab-12cd3456efg ") == "AB12CD3456EFG"
    assert normalize_vin_for_catalog_dedupe("short") == ""


def test_dedupe_key_prefers_vin():
    k = catalog_dedupe_key(
        "encar-1",
        "encar",
        {"vin": " KMHXX00XXXX000000 ", "inner_id": "99"},
    )
    assert k == "vin:KMHXX00XXXX000000"


def test_dedupe_key_inner_id_without_vin():
    k = catalog_dedupe_key("che168-x", "che168", {"che168_listing_id": "12345"})
    assert k == "che168:12345"


def test_dedupe_key_fallback_car_id():
    k = catalog_dedupe_key("only-car-id", "encar", {})
    assert k == "id:only-car-id"


def test_listing_json_inner_nested_data():
    inner = {"vin": "KMHXX00XXXX000000", "pricing_clean": {"x": 1}}
    row = {"data": {"data": inner}}
    assert listing_json_inner_from_cars_data(row["data"]) == inner


def test_listing_json_inner_flat_when_no_inner_shape():
    flat = {"vin": "KMHXX00XXXX000000", "mark": "Kia"}
    assert listing_json_inner_from_cars_data(flat) == flat


def test_listing_json_inner_from_json_string():
    import json

    inner = {"vin": "X", "identity_clean": {}}
    s = json.dumps({"data": inner})
    assert listing_json_inner_from_cars_data(s) == inner
