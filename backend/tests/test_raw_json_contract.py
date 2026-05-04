from raw_json_contract import validate_raw_json_min_contract


def test_validate_raw_json_min_contract_ok():
    data = {
        "inner_id": "1",
        "url": "http://x",
        "mark": "BMW",
        "model": "X5",
        "year": "2022",
        "engine_type": "가솔린",
        "transmission_type": "AT",
        "body_type": "SUV",
        "km_age": "10000",
        "price": "3500",
        "price_won": 35000000,
        "price_intent": "sale",
        "price_classifier_version": "v1",
        "parser_schema_version": "encar.v2",
        "data_quality": {"x": 1},
        "clean_schema_version": "encar.clean.v1",
        "identity_clean": {"car_id": "1"},
        "spec_clean": {"engine_type": "가솔린"},
        "pricing_clean": {"price_intent": "sale"},
    }
    assert validate_raw_json_min_contract(data) == {}


def test_validate_raw_json_min_contract_missing_groups():
    missing = validate_raw_json_min_contract({"inner_id": "1"})
    assert "identity" in missing
    assert "pricing" in missing
    assert "quality" in missing


def test_validate_raw_json_min_contract_che168_ok():
    data = {
        "source": "che168",
        "inner_id": "58097503",
        "mark": "BMW",
        "model": "320i",
        "price_on_request": False,
        "parser_schema_version": "che168.normalized.v1",
        "data_quality": {"x": 1},
        "clean_schema_version": "che168.clean.v1",
        "identity_clean": {"car_id": "58097503"},
        "spec_clean": {"mileage_km": ""},
        "pricing_clean": {"final_price_rub": None},
        "location_clean": {"city": ""},
        "catalog_text_clean": {"description": ""},
    }
    assert validate_raw_json_min_contract(data) == {}


def test_validate_raw_json_min_contract_che168_missing_mark():
    miss = validate_raw_json_min_contract(
        {
            "source": "che168",
            "inner_id": "1",
            "model": "X",
            "price_on_request": True,
            "parser_schema_version": "che168.normalized.v1",
            "data_quality": {},
            "clean_schema_version": "che168.clean.v1",
            "identity_clean": {},
            "spec_clean": {},
            "pricing_clean": {},
            "location_clean": {},
            "catalog_text_clean": {},
        }
    )
    assert "identity" in miss
    assert "mark" in miss["identity"]
