from __future__ import annotations

from price import CHINA_BROKER_RUB, CHINA_DOCS_DELIVERY_CNY, PriceCalculator, parse_engine_cc


def test_parse_engine_cc_supports_t_label():
    assert parse_engine_cc("1.5T") == 1500
    assert parse_engine_cc("2.0L") == 2000
    assert parse_engine_cc(1998) == 1998


def test_china_price_calc_uses_required_static_costs():
    calc = PriceCalculator(config_path="config.json")
    calc.get_cbr_cny_rub_safe = lambda: 12.0
    calc.get_cbr_eur_rub_safe = lambda: 100.0
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
    assert prices["commission_rate_default"] == 0.10
    assert prices["total_with_commission"] > prices["vehicle_sum"]
