"""Tests for USA Autotrader pricing helper."""

from __future__ import annotations

from priceusa import parse_price_usd, sync_usa_pricing_clean_block


def test_parse_price_usd_from_field() -> None:
    assert parse_price_usd({"price_usd": 53285}) == 53285.0


def test_parse_price_usd_from_pricing_detail() -> None:
    assert parse_price_usd({"pricingDetail": {"salePrice": 12000, "msrp": 13000}}) == 12000.0


def test_sync_usa_pricing_clean_block() -> None:
    data = {"my_price": 1_000_000, "pricing_tier": "full_customs"}
    sync_usa_pricing_clean_block(data)
    pc = data["pricing_clean"]
    assert pc["final_price_rub"] == 1_000_000
    assert pc["pricing_rules_version"]
    assert pc["customs_included"] is True
