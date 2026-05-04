from __future__ import annotations

from market_pricing_shared import parse_engine_cc
from pricechina import (
    CHINA_BROKER_RUB,
    CHINA_DOCS_DELIVERY_CNY,
    CHINA_PRICING_RULES_VERSION,
    PriceCalculatorChina,
    sync_china_pricing_clean_block,
)


def test_parse_engine_cc_supports_t_label():
    assert parse_engine_cc("1.5T") == 1500
    assert parse_engine_cc("2.0L") == 2000
    assert parse_engine_cc(1998) == 1998


def test_china_price_calc_uses_required_static_costs():
    calc = PriceCalculatorChina(config_path="config.json")
    calc._fx.get_cbr_cny_rub_safe = lambda: 12.0
    calc._fx.get_cbr_eur_rub_safe = lambda: 100.0
    car = {
        "source": "che168",
        "price_cny": 50000,
        "year": 2021,
        "engine_type": "Бензин",
        "displacement": "2.0T",
        "hp": 190,
    }
    prices = calc.calculate_total_cost_china(car)
    assert prices["china_docs_delivery_cny"] == CHINA_DOCS_DELIVERY_CNY
    assert prices["broker_rub"] == CHINA_BROKER_RUB
    assert prices["price_rub"] == 600_000
    assert prices["vtb_bank_transfer_rub"] == 12_000.0
    assert prices["commission_rate_default"] == 0.0
    assert prices["commission"] == 150_000
    assert prices["vehicle_sum"] == 1_638_224.0
    assert prices["total_with_commission"] == 1_788_224.0
    assert prices["total_with_commission"] > prices["vehicle_sum"]


def test_sync_china_pricing_clean_block_full_customs():
    d: dict = {
        "source": "che168",
        "pricing_tier": "full_customs",
        "my_price": 1_234_000.0,
        "pricing_clean": {"final_price_rub": 0},
    }
    sync_china_pricing_clean_block(d)
    pc = d["pricing_clean"]
    assert pc["pricing_rules_version"] == CHINA_PRICING_RULES_VERSION
    assert pc["pricing_tier"] == "full_customs"
    assert pc["final_price_rub"] == 1_234_000.0
    assert pc["customs_included"] is True


def test_sync_china_pricing_clean_block_price_on_request():
    d = {"source": "che168", "pricing_tier": "price_on_request", "price_on_request": True}
    sync_china_pricing_clean_block(d)
    pc = d["pricing_clean"]
    assert pc["pricing_rules_version"] == CHINA_PRICING_RULES_VERSION
    assert pc["price_on_request"] is True
    assert "final_price_rub" not in pc
