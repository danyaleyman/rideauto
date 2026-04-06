"""dongchedi.normalize — без сети."""

from __future__ import annotations

import json

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


def test_sku_row_nested_detail_yields_multiple_photos():
    row = {
        "sku_id": 99,
        "title": "Gallery car",
        "brand_name": "测试",
        "series_name": "S",
        "car_year": 2020,
        "car_mileage": "1万公里",
        "image": "https://example.com/cover.jpg",
    }
    detail = {
        "car_report": {
            "sections": [
                {"pics": ["https://p3-dcd.byteimg.com/a.webp", "https://p3-dcd.byteimg.com/b.jpg"]},
            ]
        },
        "extra_nested": {"thumb": "https://img.site/shot.png?x=1"},
    }
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=13.0)
    imgs = json.loads(out["data"]["images"])
    assert len(imgs) >= 3
    assert "https://example.com/cover.jpg" in imgs


def test_sku_row_detail_car_info_and_gallery():
    row = {
        "sku_id": 7,
        "title": "测试车",
        "brand_name": "宝马",
        "series_name": "3系",
        "car_year": 2018,
        "car_mileage": "",
        "image": "https://example.com/cover.jpg",
    }
    detail = {
        "car_info": {
            "mileage": "2万公里",
            "color": "黑色",
            "gear_type": "自动",
            "fuel_type": "汽油",
        },
        "image_list": [
            {"url": "https://example.com/cover.jpg"},
            {"url": "https://example.com/extra.jpg"},
        ],
    }
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=13.0)
    d = out["data"]
    assert d["km_age"] == 20000
    assert d["color"] == "黑色"
    assert d["transmission_type"] == "自动"
    assert d["engine_type"] == "汽油"
    imgs = json.loads(d["images"])
    assert imgs[0] == "https://example.com/cover.jpg"
    assert "https://example.com/extra.jpg" in imgs


def test_row_protocol_relative_image_normalized():
    row = {
        "sku_id": 1,
        "title": "T",
        "brand_name": "B",
        "series_name": "S",
        "car_year": 2020,
        "car_mileage": "1万公里",
        "image": "//p3.dcarimg.com/img/motor/foo~1200x0.jpg",
    }
    out = sku_row_to_payload(row, detail=None, cny_to_rub=13.0)
    imgs = json.loads(out["data"]["images"])
    assert len(imgs) == 1
    assert imgs[0].startswith("https://")


def test_detail_other_params_car_config_and_listing_meta():
    row = {
        "sku_id": 55,
        "title": "宝马X1",
        "brand_name": "宝马",
        "series_name": "宝马X1",
        "car_year": 2018,
        "car_mileage": "7万公里",
        "image": "https://example.com/c.jpg",
        "car_name": "sDrive18Li",
        "transfer_cnt": 1,
        "car_source_city_name": "上海",
    }
    detail = {
        "source_sh_price": 30260000,
        "important_text": "2019年上牌 | 7.06万公里 | 北京车源",
        "head_images": ["https://example.com/h1.jpg"],
        "other_params": [
            {"name": "上牌时间", "value": "2019年06月"},
            {"name": "过户次数", "value": "2次"},
            {"name": "排量", "value": "1.5T"},
            {"name": "内饰颜色", "value": "浅色"},
            {"name": "车源地", "value": "北京"},
        ],
        "car_config_overview": {
            "car_name": "sDrive18Li 时尚型",
            "manipulation": {"driver_form": "前置前驱"},
            "power": {
                "horsepower": "136马力",
                "fuel_form": "汽油",
                "gearbox_description": "6挡手自一体",
                "capacity": "1.5T",
            },
        },
    }
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=10.0)
    d = out["data"]
    assert d["year"] == "2019"
    assert d["yearMonth"] == "201906"
    assert d["transfer_count"] == 2
    assert d["city"] == "北京"
    assert d["dongchedi_displacement_label"] == "1.5T"
    assert d["hp"] == 136
    assert d["drive_type"] == "前置前驱"
    assert d["interior_color"] == "浅色"
    assert d["configuration"] == "sDrive18Li 时尚型"
    assert d["dongchedi_summary"] == "2019年上牌 | 7.06万公里 | 北京车源"
    imgs = json.loads(d["images"])
    assert "https://example.com/h1.jpg" in imgs
