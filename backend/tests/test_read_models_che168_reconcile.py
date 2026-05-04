from read_models import build_catalog_read_model


def test_che168_reconcile_shows_price_when_my_price_present():
    data = {
        "source": "che168",
        "price_on_request": True,
        "pricing_tier": "price_on_request",
        "pricing_clean": {"pricing_tier": "price_on_request", "final_price_rub": 1_500_000},
        "price_cny": 250000,
        "my_price": 1_500_000,
    }
    rm = build_catalog_read_model(data, use_clean=True)
    assert rm["pricing_tier"] == "full_customs"
    assert rm["price_on_request"] is False
    assert rm["price_rub"] == 1_500_000.0
