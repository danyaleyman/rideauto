from fastapi_app.catalog_slim import slim_catalog_car


def test_slim_does_not_force_price_on_request_by_finance_text_only():
    car = {
        "data": {
            "source": "encar",
            "mark": "Hyundai",
            "model": "Kona",
            "year": "2026",
            "km_age": "1",
            "my_price": 1022243,
            "price_won": 4320000,
            "price_text": "월36만원 월렌트(12개월) 인수금 0만원 차량가격 432만원",
        }
    }
    out = slim_catalog_car(car, "encar-1")
    assert out.get("price") == 1022243
    assert out.get("price_on_request") in (False, None)


def test_slim_keeps_normal_price_for_regular_card():
    car = {
        "data": {
            "source": "encar",
            "mark": "Hyundai",
            "model": "Avante",
            "year": "2018",
            "km_age": "98000",
            "my_price": 1190000,
            "price_won": 95000000,
            "price": "9500",
        }
    }
    out = slim_catalog_car(car, "encar-2")
    assert out.get("price") is not None
    assert out.get("price_on_request") in (False, None)


def test_slim_keeps_normal_price_for_regular_card_with_finance_promo_text():
    car = {
        "data": {
            "source": "encar",
            "mark": "Lamborghini",
            "model": "Urus",
            "year": "2025",
            "km_age": "1384",
            "my_price": 49600445,
            "price_won": 450900000,
            "price": "45090",
            "price_text": "엔카금융 1분만에 한도/금리 비교",
        }
    }
    out = slim_catalog_car(car, "encar-3")
    assert out.get("price") == 49600445
    assert out.get("price_on_request") in (False, None)


def test_slim_prefers_pricing_clean_when_present(monkeypatch):
    monkeypatch.setenv("WRA_CLEAN_READ_MODE", "1")
    monkeypatch.setenv("WRA_CLEAN_READ_PERCENT", "100")
    from fastapi_app.config import get_settings

    get_settings.cache_clear()
    car = {
        "data": {
            "source": "encar",
            "mark": "Kia",
            "model": "K8",
            "my_price": 1000,
            "pricing_clean": {
                "final_price_rub": 2000,
                "reserved_placeholder": True,
            },
        }
    }
    out = slim_catalog_car(car, "encar-4")
    assert out.get("price") == 2000
    assert out.get("price_on_request") in (False, None)
    assert out.get("encar_listing_reserved") is True
    get_settings.cache_clear()


def test_slim_uses_legacy_when_clean_mode_off(monkeypatch):
    monkeypatch.delenv("WRA_CLEAN_READ_MODE", raising=False)
    from fastapi_app.config import get_settings

    get_settings.cache_clear()
    car = {
        "data": {
            "source": "encar",
            "mark": "Kia",
            "model": "K8",
            "my_price": 1000,
            "pricing_clean": {
                "final_price_rub": 2000,
                "price_on_request": True,
            },
        }
    }
    out = slim_catalog_car(car, "encar-5")
    # Как в read_models: final_price_rub из pricing_clean используется даже при clean-read выключен
    assert out.get("price") == 2000
    assert out.get("price_on_request") in (False, None)
    get_settings.cache_clear()


def test_slim_includes_vin_in_data_for_catalog_dedupe():
    car = {
        "data": {
            "source": "encar",
            "mark": "Kia",
            "model": "K7",
            "vin": "KNALC41BBMA240855",
        }
    }
    out = slim_catalog_car(car, "encar-vin")
    assert out["data"].get("vin") == "KNALC41BBMA240855"
