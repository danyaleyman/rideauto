"""cars.source NOT NULL: row_to_car_fields must never omit source (postgres_catalog_sync path)."""

import pytest

from catalog_pg_core import row_to_car_fields


def test_row_to_car_fields_defaults_encar_when_data_has_no_source():
    payload = {"data": {"mark": "벤츠", "model": "S", "id": "41591957"}}
    f = row_to_car_fields("41591957", payload)
    assert f["source"] == "encar"


def test_row_to_car_fields_dongchedi_prefix_without_inner_source():
    cid = "dongchedi-abc-1"
    payload = {"data": {"mark": "X", "model": "Y", "id": cid}}
    f = row_to_car_fields(cid, payload)
    assert f["source"] == "dongchedi"


def test_row_to_car_fields_respects_inner_source():
    payload = {"data": {"mark": "M", "model": "N", "source": "dongchedi"}}
    f = row_to_car_fields("x-1", payload)
    assert f["source"] == "dongchedi"


def test_row_to_car_fields_prefers_clean_layers_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WRA_CLEAN_READ_MODE", "1")
    payload = {
        "data": {
            "mark": "legacy-mark",
            "model": "legacy-model",
            "my_price": 1111,
            "identity_clean": {"mark": "BMW", "model": "X5", "year": "2024"},
            "spec_clean": {"engine_type": "가솔린", "mileage_km": "15000"},
            "pricing_clean": {"final_price_rub": 2222},
            "condition_clean": {"insurance_cases": 3, "damaged_parts_count": 2},
        }
    }
    f = row_to_car_fields("encar-1", payload)
    assert f["mark"] == "BMW"
    assert f["model"] == "X5"
    assert f["price_rub"] == 2222.0
    assert f["mileage_km"] == 15000
    assert f["insurance_cases"] == 3
    assert f["damaged_parts_count"] == 2


def test_row_to_car_fields_encar_trim_no_configuration_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WRA_CLEAN_READ_MODE", raising=False)
    payload = {
        "data": {
            "source": "encar",
            "mark": "X",
            "model": "Y",
            "configuration": "Badge trim only",
            "generation": "G1",
            "modelGroupName": "Y LineUp",
        }
    }
    f = row_to_car_fields("41900001", payload)
    assert f["trim_name"] is None
    assert f["encar_model_group"] == "Y LineUp"


def test_row_to_car_fields_encar_gradeName_trim(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WRA_CLEAN_READ_MODE", raising=False)
    payload = {
        "data": {
            "source": "encar",
            "mark": "Kia",
            "model": "EV6",
            "gradeName": "GT-Line AWD",
            "configuration": "should not leak",
            "modelGroupName": "EV Group",
        }
    }
    f = row_to_car_fields("41877280", payload)
    assert f["trim_name"] == "GT-Line AWD"
    assert f["encar_model_group"] == "EV Group"


def test_row_to_car_fields_dongchedi_trim_configuration_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WRA_CLEAN_READ_MODE", raising=False)
    payload = {
        "data": {"source": "dongchedi", "mark": "B", "model": "M", "configuration": "330Li"}
    }
    f = row_to_car_fields("dongchedi-z", payload)
    assert f["trim_name"] == "330Li"
    assert f["encar_model_group"] is None


def test_row_to_car_fields_legacy_when_clean_mode_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WRA_CLEAN_READ_MODE", raising=False)
    payload = {
        "data": {
            "mark": "legacy-mark",
            "model": "legacy-model",
            "my_price": 1111,
            "identity_clean": {"mark": "BMW", "model": "X5"},
            "pricing_clean": {"final_price_rub": 2222},
        }
    }
    f = row_to_car_fields("encar-1", payload)
    assert f["mark"] == "legacy-mark"
    assert f["model"] == "legacy-model"
    assert f["price_rub"] == 1111.0
