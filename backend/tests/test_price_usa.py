"""Tests for USA Autotrader pricing helper."""

from __future__ import annotations

from market_pricing_shared import parse_engine_cc
from priceusa import (
    PriceCalculatorUsa,
    parse_price_usd,
    sync_usa_pricing_clean_block,
    usa_has_customs_inputs,
)


def test_parse_price_usd_from_field() -> None:
    assert parse_price_usd({"price_usd": 53285}) == 53285.0


def test_parse_price_usd_from_pricing_detail() -> None:
    assert parse_price_usd({"pricingDetail": {"salePrice": 12000, "msrp": 13000}}) == 12000.0


def test_parse_engine_cc_liters_float_and_string() -> None:
    # Autotrader displacementUOM is liters; must not truncate 1.6 → 1.
    assert parse_engine_cc(1.6) == 1600
    assert parse_engine_cc(2.0) == 2000
    assert parse_engine_cc("1.6") == 1600
    assert parse_engine_cc("1.6 L") == 1600
    assert parse_engine_cc(1998) == 1998


def test_sync_usa_pricing_clean_block() -> None:
    data = {"my_price": 1_000_000, "pricing_tier": "full_customs"}
    sync_usa_pricing_clean_block(data)
    pc = data["pricing_clean"]
    assert pc["final_price_rub"] == 1_000_000
    assert pc["pricing_rules_version"]
    assert pc["customs_included"] is True


def test_usa_has_customs_inputs_requires_cc_and_hp() -> None:
    assert not usa_has_customs_inputs({"engine_type": "Gasoline", "price_usd": 20000})
    assert not usa_has_customs_inputs(
        {"engine_type": "Gasoline", "displacement_cc": 2000, "price_usd": 20000}
    )
    assert usa_has_customs_inputs(
        {
            "engine_type": "Gasoline",
            "displacement_cc": 2000,
            "power_hp": 180,
            "price_usd": 20000,
        }
    )


def test_usa_update_por_without_engine_specs() -> None:
    calc = PriceCalculatorUsa(config_path="config.json")
    car = {
        "source": "autotrader",
        "price_usd": 25000,
        "year": 2021,
        "engine_type": "Gasoline",
    }
    out = calc.update_usa_car_with_prices(car)
    assert out["price_on_request"] is True
    assert out["pricing_tier"] == "price_on_request"
    assert out.get("usa_customs_inputs_missing") is True
    assert out.get("my_price") is None


def test_usa_full_customs_with_real_specs() -> None:
    calc = PriceCalculatorUsa(config_path="config.json")
    calc._fx.get_cbr_usd_rub_exclusive = lambda: 95.0  # type: ignore[method-assign]
    calc._fx.get_cbr_eur_rub_safe = lambda: 105.0  # type: ignore[method-assign]
    car = {
        "source": "autotrader",
        "price_usd": 25000,
        "year": 2021,
        "engine_type": "Gasoline",
        "displacement_cc": 2000,
        "power_hp": 180,
    }
    out = calc.update_usa_car_with_prices(car)
    assert out["price_on_request"] is False
    assert out["pricing_tier"] == "full_customs"
    assert out["my_price"] and out["my_price"] > 0
    assert out["customs_total_rub"] and out["customs_total_rub"] > 0
    assert out.get("usa_customs_inputs_missing") is None
