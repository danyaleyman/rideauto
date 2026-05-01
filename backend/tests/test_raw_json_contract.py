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
