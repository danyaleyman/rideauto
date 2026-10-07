"""Unit tests for Autotrader parser (fixtures, no live network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scraper_pipeline.autotrader.parser import (
    car_id_for_listing,
    extract_next_data,
    normalize_listing,
    parse_srp_page,
    parse_vdp_page,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "autotrader"


@pytest.fixture(scope="module")
def srp_html() -> str:
    return (FIX / "srp_all_cars_min.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def vdp_html() -> str:
    return (FIX / "vdp_789850281_min.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def vdp_listing() -> dict:
    return json.loads((FIX / "vdp_listing_789850281.json").read_text(encoding="utf-8"))


def test_extract_next_data(srp_html: str) -> None:
    nd = extract_next_data(srp_html)
    assert nd is not None
    assert "props" in nd


def test_parse_srp_page(srp_html: str) -> None:
    parsed = parse_srp_page(srp_html)
    assert parsed["ok"] is True
    assert len(parsed["active_ids"]) == 5
    assert parsed["total_count"] and parsed["total_count"] > 1000
    for lid in parsed["active_ids"]:
        assert lid in parsed["inventory"]


def test_parse_vdp_page(vdp_html: str) -> None:
    parsed = parse_vdp_page(vdp_html, listing_id="789850281")
    assert parsed["ok"] is True
    assert parsed["listing_id"] == "789850281"
    assert parsed["listing"]["vin"]


def test_normalize_vdp_listing(vdp_listing: dict) -> None:
    car = normalize_listing(vdp_listing, listing_id="789850281", depth="vdp")
    assert car["source"] == "autotrader"
    assert car_id_for_listing("789850281") == "autotrader-789850281"
    assert car["mark"] == "Hyundai"
    assert car["model"] == "Santa Fe"
    assert car["year"] == 2027
    assert car["vin"] == "5NMP5DG1XVH150467"
    assert car["price_usd"] == 53285
    assert car["mileage_miles"] == 3
    assert car["km_age"] == 5  # round(3 * 1.609344)
    assert car["configuration"] == "Calligraphy"
    assert isinstance(car["features"], list) and len(car["features"]) > 10
    assert len(car["images"]) >= 1
    assert car["dealer_city"] == "Hyannis"
    assert car["dealer_state"] == "MA"
