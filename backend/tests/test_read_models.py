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


def test_encar_reconciles_stale_por_using_spec_clean_displacement_only(monkeypatch):
    """Объём только в spec_clean (как после clean-слоя без корня) — всё равно korea_land_only для ICE без л.с."""
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    d = {
        "source": "encar",
        "price_won": 12_000_000,
        "engine_type": "gasoline",
        "spec_clean": {"displacement_cc": "998", "engine_type": "gasoline"},
        "my_price": 1_800_000.0,
        "pricing_clean": {"pricing_tier": "price_on_request", "price_on_request": True},
    }
    rm = build_catalog_read_model(d, use_clean=True)
    assert rm["pricing_tier"] == "korea_land_only"
    assert rm["price_on_request"] is False
    assert rm["customs_included"] is False
    assert rm["price_rub"] == 1_800_000.0


def test_final_price_rub_from_pricing_clean_when_clean_read_off(monkeypatch):
    """WRA_CLEAN_READ_PERCENT=0 → use_clean=False; цена в списке всё равно из pricing_clean."""
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    d = {
        "source": "encar",
        "price_won": 28_500_000,
        "engine_type": "gasoline",
        "power_hp": 180,
        "displacement": 1598,
        "pricing_clean": {"final_price_rub": 4_200_000.0, "pricing_tier": "full_customs"},
    }
    rm = build_catalog_read_model(d, use_clean=False)
    assert rm["price_rub"] == 4_200_000.0
    assert rm["price_on_request"] is False


def test_power_hp_falls_back_to_encar_power_root(monkeypatch):
    """Encar кладёт л.с. в `power`; без spec_clean legacy-путь раньше давал null."""
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    d = {
        "source": "encar",
        "mark": "Hyundai",
        "power": "180",
        "pricing_clean": {"final_price_rub": 1.0, "pricing_tier": "full_customs"},
    }
    rm = build_catalog_read_model(d, use_clean=False)
    assert rm["power_hp"] == 180


def test_power_hp_normalized_from_spec_clean_string(monkeypatch):
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    d = {
        "source": "encar",
        "spec_clean": {"power_hp": "198"},
        "pricing_clean": {"final_price_rub": 1.0, "pricing_tier": "full_customs"},
    }
    rm = build_catalog_read_model(d, use_clean=True)
    assert rm["power_hp"] == 198


def test_che168_reconciles_tier_when_buyer_price_present(monkeypatch):
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    d = {
        "source": "che168",
        "price_won": 28_500_000,
        "engine_type": "gasoline",
        "power_hp": 180,
        "displacement": 1598,
        "my_price": 3_500_000.0,
        "pricing_clean": {"pricing_tier": "price_on_request", "price_on_request": True},
    }
    rm = build_catalog_read_model(d, use_clean=True)
    assert rm["pricing_tier"] == "full_customs"
    assert rm["price_rub"] == 3_500_000.0

