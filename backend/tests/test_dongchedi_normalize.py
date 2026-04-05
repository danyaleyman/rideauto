"""dongchedi.normalize — без сети."""

from __future__ import annotations

from dongchedi.normalize import row_matches_filters, sku_row_to_payload


def test_sku_row_to_payload_with_detail_fen():
    row = {
        "sku_id": 123,
        "title": "宝马3系 2020款 325Li",
        "brand_name": "宝马",
        "series_name": "宝马3系",
        "series_id": 145,
        "brand_id": 4,
        "car_year": 2020,
        "car_mileage": "3.5万公里",
        "image": "https://example.com/a.jpg",
    }
    detail = {"source_sh_price": 8880000}
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=10.0)
    d = out["data"]
    assert d["source"] == "dongchedi"
    assert d["inner_id"] == "123"
    assert d["price_cny"] == 88800.0
    assert d["my_price"] == 888000.0
    assert d["km_age"] == 35000
    assert "images" in d


def test_row_matches_series_and_year():
    row = {"series_id": 145, "car_year": 2019}
    assert row_matches_filters(row, series_id=145, year_min=2018, year_max=2020)
    assert not row_matches_filters(row, series_id=999, year_min=2018, year_max=2020)
    assert not row_matches_filters(row, series_id=145, year_min=2020, year_max=2021)
