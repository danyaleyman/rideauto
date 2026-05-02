from read_models import build_catalog_read_model


def test_read_model_prefers_clean_and_fallbacks(monkeypatch):
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    d = {
        "mark": "legacy-mark",
        "my_price": 1000,
        "identity_clean": {"mark": "BMW"},
        "pricing_clean": {"final_price_rub": 2000},
    }
    rm = build_catalog_read_model(d, use_clean=True)
    assert rm["mark"] == "BMW"
    assert rm["price_rub"] == 2000.0


def test_read_model_without_legacy_fallback(monkeypatch):
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "0")
    d = {"mark": "legacy-mark"}
    rm = build_catalog_read_model(d, use_clean=True)
    assert rm["mark"] == ""


def test_encar_reconciles_stale_price_on_request_to_full_customs(monkeypatch):
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    d = {
        "source": "encar",
        "price_won": 28_500_000,
        "engine_type": "gasoline",
        "power_hp": 180,
        "displacement": 1598,
        "my_price": 3_500_000.0,
        "pricing_clean": {
            "pricing_tier": "price_on_request",
            "price_on_request": True,
            "customs_included": False,
        },
    }
    rm = build_catalog_read_model(d, use_clean=True)
    assert rm["pricing_tier"] == "full_customs"
    assert rm["price_on_request"] is False
    assert rm["customs_included"] is True
    assert rm["price_rub"] == 3_500_000.0


def test_encar_does_not_reconcile_dongchedi(monkeypatch):
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    d = {
        "source": "dongchedi",
        "price_won": 28_500_000,
        "engine_type": "gasoline",
        "power_hp": 180,
        "displacement": 1598,
        "my_price": 3_500_000.0,
        "pricing_clean": {"pricing_tier": "price_on_request", "price_on_request": True},
    }
    rm = build_catalog_read_model(d, use_clean=True)
    assert rm["pricing_tier"] == "price_on_request"

