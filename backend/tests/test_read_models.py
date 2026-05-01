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

