import pytest

from scraper_pipeline.che168.parser import (
    che168_listing_numeric_id,
    normalize_price_cny,
    parse_one_che168_car_sync,
)


def test_che168_listing_numeric_id():
    assert che168_listing_numeric_id({"id": 42}) == "42"
    assert che168_listing_numeric_id({"infoId": "99"}) == "99"
    assert che168_listing_numeric_id({}) == ""


def test_normalize_price_cny_wan():
    assert normalize_price_cny(25.8, assume_wan_yuan=True) == 258000.0
    assert normalize_price_cny(258000, assume_wan_yuan=False) == 258000.0


def test_normalize_price_cny_heuristic_small_float():
    v = normalize_price_cny(12.8, assume_wan_yuan=False)
    assert v == 128000.0


def test_parse_one_che168_minimal():
    car = parse_one_che168_car_sync(
        external_id="58097503",
        list_item={"id": 58097503, "brandname": "BMW", "modelname": "320i", "price": 258000},
        carinfo={
            "title": "BMW 320i",
            "price": 258000,
            "images": ["https://erscglobal2.autoimg.cn/escimg/auto/x.jpg.webp"],
            "vin": "WBA12345678901234",
            "specid": 46481,
        },
        specparam={"displacement": "2.0T", "gearbox": "AT", "fueltype": "Gasoline"},
        specconfig={"list": [{"name": "Sunroof"}]},
        recommend=None,
        report_summary=None,
        assume_price_wan_yuan=False,
    )
    assert car is not None
    assert car["id"] == "che168-58097503"
    d = car["data"]
    assert d["source"] == "che168"
    assert d["price_cny"] == 258000.0
    assert d["mark"] == "BMW"
    assert d["vin"] == "WBA12345678901234"
    assert d["images"][0].endswith(".webp")
    assert "Sunroof" in (d.get("che168_recommended_options") or [])
    assert d.get("clean_schema_version") == "che168.clean.v1"
    assert isinstance(d.get("identity_clean"), dict)
    assert d.get("che168_price_cny_rule") == "raw_cny_integer"
    assert "completeness" in (d.get("data_quality") or {})
    assert not (d.get("data_quality") or {}).get("contract_violations")
    assert d.get("raw_envelope", {}).get("raw_schema_version") == "che168.raw.v1"
    assert car.get("_raw", {}).get("sources", {}).get("list_item") == {"id": 58097503, "brandname": "BMW", "modelname": "320i", "price": 258000}


def test_parse_one_merges_list_images_when_carinfo_has_none():
    car = parse_one_che168_car_sync(
        external_id="99",
        list_item={"id": 99, "picurl": "https://example.com/list.jpg", "brandname": "X", "price": 200000},
        carinfo={"price": 200000, "brandname": "X"},
        specparam=None,
        specconfig=None,
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    imgs = car["data"].get("images") or []
    assert any("list.jpg" in u for u in imgs)


def test_taxonomy_aliases():
    car = parse_one_che168_car_sync(
        external_id="1",
        list_item={"brandname": "Foo Display", "price": 100000},
        carinfo={"price": 100000, "brandname": "Foo Display"},
        specparam=None,
        specconfig=None,
        recommend=None,
        report_summary=None,
        taxonomy={"mark_aliases": {"foo display": "Foo"}},
    )
    assert car["data"].get("mark_canonical") == "Foo"


def test_taxonomy_brand_by_id_overrides_mark():
    car = parse_one_che168_car_sync(
        external_id="1",
        list_item={"brandid": 15, "brandname": "Wrong", "price": 100000},
        carinfo={"brandid": 15, "price": 100000, "brandname": "Wrong"},
        specparam=None,
        specconfig=None,
        recommend=None,
        report_summary=None,
        taxonomy={"brand_by_id": {"15": "BMW"}},
    )
    assert car["data"].get("mark_canonical") == "BMW"


def test_parse_one_che168_missing_mark_still_structured():
    car = parse_one_che168_car_sync(
        external_id="1",
        list_item={"price": 100000},
        carinfo={"price": 100000},
        specparam=None,
        specconfig=None,
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    dq = car["data"].get("data_quality") or {}
    assert "mark" in (dq.get("missing_required_fields") or [])
    cv = dq.get("contract_violations") or {}
    assert "identity" in cv
    assert "mark" in cv["identity"]
    assert "raw_json_min_contract_violation" in (dq.get("reasons") or [])
