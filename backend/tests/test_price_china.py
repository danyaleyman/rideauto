from __future__ import annotations

from market_pricing_shared import parse_engine_cc
from pricechina import CHINA_BROKER_RUB, CHINA_DOCS_DELIVERY_CNY, PriceCalculatorChina


def test_parse_engine_cc_supports_t_label():
    assert parse_engine_cc("1.5T") == 1500
    assert parse_engine_cc("2.0L") == 2000
    assert parse_engine_cc(1998) == 1998


def test_china_price_calc_uses_required_static_costs():
    calc = PriceCalculatorChina(config_path="config.json")
    calc._fx.get_cbr_cny_rub_safe = lambda: 12.0
    calc._fx.get_cbr_eur_rub_safe = lambda: 100.0
    car = {
        "source": "dongchedi",
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
    assert prices["commission_rate_default"] == 0.0
    assert prices["commission"] == 150_000
    assert prices["total_with_commission"] > prices["vehicle_sum"]
