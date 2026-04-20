"""dongchedi.normalize — без сети."""

from __future__ import annotations

import json

from dongchedi.normalize import row_matches_filters, sku_row_to_payload
from dongchedi.parse_detail import parse_params_raw_data_from_html, parse_sku_detail_from_html


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
    assert d["color"] in ("黑色", "Черный")
    assert d["transmission_type"] in ("自动", "Автоматическая")
    assert d["engine_type"] in ("汽油", "Бензин")
    imgs = json.loads(d["images"])
    assert imgs[0] == "https://example.com/cover.jpg"
    assert "https://example.com/extra.jpg" in imgs


def test_km_from_important_text_and_spaced_wan_km():
    row = {
        "sku_id": 23134642,
        "title": "福睿斯",
        "brand_name": "福特",
        "series_name": "福睿斯",
        "car_year": 2015,
        "car_mileage": "",
        "image": "https://example.com/c.jpg",
    }
    detail = {
        "important_text": "2015|06 · 【行驶里程】6.68万 公里 · 南宁",
        "other_params": [{"name": "内饰颜色", "value": "浅色"}],
    }
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=13.0)
    assert out["data"]["km_age"] == 66800


def test_km_from_other_params_and_plain_km():
    row = {
        "sku_id": 2,
        "title": "T",
        "brand_name": "B",
        "series_name": "S",
        "car_year": 2020,
        "car_mileage": "",
        "image": "https://example.com/x.jpg",
    }
    detail = {"other_params": [{"name": "行驶里程", "value": "120500公里"}]}
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=13.0)
    assert out["data"]["km_age"] == 120500


def test_parse_detail_injects_mileage_hint_from_raw_html():
    payload = {
        "props": {
            "pageProps": {
                "skuDetail": {"car_info": {}},
            }
        }
    }
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload, ensure_ascii=False)
        + "</script>车况【行驶里程】6.68万公里介绍"
    )
    sd = parse_sku_detail_from_html(html)
    assert sd is not None
    assert sd.get("_mileage_hint_km") == 66800
    row = {
        "sku_id": 99,
        "title": "X",
        "brand_name": "B",
        "series_name": "S",
        "car_year": 2015,
        "car_mileage": "",
        "image": "https://example.com/z.jpg",
    }
    out = sku_row_to_payload(row, detail=sd, cny_to_rub=13.0)
    assert out["data"]["km_age"] == 66800


def test_parse_detail_fallback_when_sku_detail_missing():
    payload = {
        "props": {
            "pageProps": {
                "rawData": {
                    "car_info": {"mileage": "2.3万公里"},
                    "image_list": [{"url": "https://example.com/1.jpg"}, {"url": "https://example.com/2.jpg"}],
                    "source_sh_price": 1230000,
                }
            }
        }
    }
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload, ensure_ascii=False)
        + "</script>"
    )
    sd = parse_sku_detail_from_html(html)
    assert sd is not None
    assert isinstance(sd.get("car_info"), dict)
    assert isinstance(sd.get("image_list"), list)


def test_parse_detail_from_raw_html_sku_detail_blob():
    html = """
    <html><body>
    <script>window.__x = {"other":1,"skuDetail":{"car_info":{"mileage":"1.2万公里"},"image_list":[{"url":"https://example.com/a.jpg"},{"url":"https://example.com/b.jpg"}]}};</script>
    </body></html>
    """
    sd = parse_sku_detail_from_html(html)
    assert sd is not None
    assert isinstance(sd.get("car_info"), dict)
    assert isinstance(sd.get("image_list"), list)


def test_parse_detail_from_escaped_sku_detail_blob():
    html = r"""
    <html><body>
    <script>window.__x = "{\"skuDetail\":{\"car_info\":{\"mileage\":\"1.2万公里\"},\"source_sh_price\":1230000}}";</script>
    </body></html>
    """
    sd = parse_sku_detail_from_html(html)
    assert sd is not None
    assert isinstance(sd.get("car_info"), dict)
    assert sd.get("source_sh_price") == 1230000


def test_parse_params_raw_data_when_not_in_pageprops():
    payload = {
        "props": {
            "alt": {
                "nested": {
                    "rawData": {
                        "car_info": {
                            "car_id": 36968,
                            "info": {"max_power": {"value": "167(227Ps)"}},
                        }
                    }
                }
            }
        }
    }
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload, ensure_ascii=False)
        + "</script>"
    )
    rd = parse_params_raw_data_from_html(html)
    assert rd is not None
    assert isinstance(rd.get("car_info"), dict)
    assert rd["car_info"].get("car_id") == 36968


def test_km_from_car_info_mileage_int():
    row = {
        "sku_id": 3,
        "title": "T",
        "brand_name": "B",
        "series_name": "S",
        "car_year": 2019,
        "car_mileage": "",
        "image": "https://example.com/y.jpg",
    }
    detail = {"car_info": {"mileage": 45600}}
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=13.0)
    assert out["data"]["km_age"] == 45600


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
    assert d["drive_type"] in ("前置前驱", "Передний привод")
    assert d["interior_color"] == "浅色"
    assert d["configuration"] == "sDrive18Li 时尚型"
    assert d["dongchedi_summary"] == "2019年上牌 | 7.06万公里 | 北京车源"
    imgs = json.loads(d["images"])
    assert "https://example.com/h1.jpg" in imgs


def test_sku_row_params_raw_merges_msrp_and_specs_url():
    row = {
        "sku_id": 23134642,
        "title": "福睿斯",
        "brand_name": "福特",
        "series_name": "福睿斯",
        "car_year": 2015,
        "car_mileage": "6.68万公里",
        "image": "https://example.com/c.jpg",
    }
    detail = {
        "source_sh_price": 15000000,
        "car_info": {"car_id": 8520},
        "_params_raw": {
            "car_info": {
                "car_id": 8520,
                "car_name": "福睿斯 2015款 1.5L 自动时尚型",
                "car_year": 2015,
                "official_price": "11.98万",
                "info": {
                    "market_time": {"value": "2014.12"},
                    "wheelbase": {"value": "2687"},
                    "gearbox_description": {"value": "6挡手自一体"},
                },
            }
        },
    }
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=13.0)
    d = out["data"]
    assert d["dongchedi_specs_url"] == "https://www.dongchedi.com/auto/params-carIds-8520"
    assert d["configuration"] == "福睿斯 2015款 1.5L 自动时尚型"
    assert d["dongchedi_model_year"] == "2015"
    assert d["dongchedi_market_time"] == "2014.12"
    assert d["dongchedi_msrp_cny"] == 119800.0
    assert d["dongchedi_msrp_rub"] == 1557400
    assert "dongchedi_params_raw" in d
    raw = json.loads(d["dongchedi_params_raw"])
    assert isinstance(raw, dict)
    assert raw.get("car_info", {}).get("car_id") == 8520
    hl = json.loads(d["dongchedi_specs_highlights"])
    assert any(x["key"] == "wheelbase" for x in hl)


def test_row_image_kept_when_only_noisy_cover_exists():
    row = {
        "sku_id": 404,
        "title": "测试车",
        "brand_name": "测试",
        "series_name": "测试系",
        "car_year": 2020,
        "car_mileage": "1万公里",
        "image": "https://example.com/watermark-cover.jpg",
    }
    out = sku_row_to_payload(row, detail=None, cny_to_rub=13.0)
    imgs = json.loads(out["data"]["images"])
    assert imgs and imgs[0] == "https://example.com/watermark-cover.jpg"


def test_china_generation_trim_and_specs_numbers_from_params_raw():
    row = {
        "sku_id": 888,
        "title": "魏牌 VV7 2019款 升级款 2.0T 旗舰型 国VI",
        "brand_name": "魏牌",
        "series_name": "VV7",
        "car_name": "升级款 2.0T 旗舰型 国VI",
        "car_year": 2019,
        "car_mileage": "8万公里",
        "image": "https://example.com/vv7.jpg",
    }
    detail = {
        "_params_raw": {
            "car_info": {
                "car_id": 36968,
                "car_name": "升级款 2.0T 旗舰型 国VI",
                "car_year": 2019,
                "info": {
                    "max_power": {"value": "167(227Ps)"},
                    "max_torque": {"value": "385"},
                    "gearbox_description": {"value": "7挡双离合"},
                    "body_struct": {"value": "5门5座SUV"},
                    "fuel_label": {"value": "汽油"},
                },
            }
        }
    }
    out = sku_row_to_payload(row, detail=detail, cny_to_rub=13.0)
    d = out["data"]
    assert d["model"] == "VV7"
    assert d["generation"] == "升级款"
    assert d["trim_name"] == "2.0T 旗舰型 国VI"
    assert d["transmission_type"] == "7挡双离合"
    assert d["body_type"] == "5门5座SUV"
    assert d["power_kw"] == 167
    assert d["hp"] == 227
    assert d["torque_nm"] == 385
