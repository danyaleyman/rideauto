import pytest

from scraper_pipeline.che168.parser import (
    _extract_real_options,
    _extract_power_from_engine_text,
    _normalize_che168_drive,
    _normalize_che168_transmission,
    _year_from_yearname,
    che168_listing_numeric_id,
    extract_gallery_urls_from_detail_html,
    merge_che168_api_carinfo_envelope,
    merge_che168_image_url_lists,
    normalize_price_cny,
    normalize_price_cny_detailed,
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


def test_normalize_price_cny_heuristic_medium_wan_x1000():
    """Che168 Global: 10.77万 часто приходит как 10770 (万 * 1000)."""
    p, meta = normalize_price_cny_detailed(10770, assume_wan_yuan=False)
    assert p == 107700.0
    assert meta["che168_price_cny_rule"] == "heuristic_medium_wan_x1000"
    assert normalize_price_cny(258000, assume_wan_yuan=False) == 258000.0


def test_normalize_price_cny_overflow_div_1000():
    """Завышенные raw (×1000) приводятся к реалистичному диапазону б/у авто."""
    p, meta = normalize_price_cny_detailed(175_000_000, assume_wan_yuan=False)
    assert p == 175_000.0
    assert meta["che168_price_cny_rule"] == "heuristic_overflow_div_1000"


def test_extract_real_options_skips_basic_specs_paramtypeitems():
    spec = {
        "result": {
            "paramtypeitems": [
                {
                    "name": "Basic specifications",
                    "paramitems": [
                        {"name": "Engine displacement", "value": "3.0T"},
                        {"name": "Max Power (hp)", "value": "340"},
                        {"name": "Drive mode", "value": "RWD"},
                    ],
                },
                {
                    "name": "Comfort",
                    "paramitems": [{"name": "Heated steering wheel", "value": "Yes"}],
                },
            ]
        }
    }
    out = _extract_real_options(spec)
    assert "Подогрев руля" in out
    assert "Engine displacement" not in out
    assert "3.0T" not in out
    assert "RWD" not in out


def test_normalize_price_cny_embedded_wan_in_context():
    v = normalize_price_cny(
        1,
        assume_wan_yuan=False,
        price_context="标价 117.35 万",
    )
    assert v == 1_173_500.0


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
    assert "Люк" in (d.get("che168_recommended_options") or []) or "Sunroof" in (d.get("che168_recommended_options") or [])
    assert "Люк" in (d.get("options_real") or []) or "Sunroof" in (d.get("options_real") or [])
    assert d.get("clean_schema_version") == "che168.clean.v1"
    assert isinstance(d.get("identity_clean"), dict)
    assert d.get("che168_price_cny_rule") == "raw_cny_integer"
    assert "completeness" in (d.get("data_quality") or {})
    assert not (d.get("data_quality") or {}).get("contract_violations")
    assert d.get("raw_envelope", {}).get("raw_schema_version") == "che168.raw.v1"
    assert car.get("_raw", {}).get("sources", {}).get("list_item") == {"id": 58097503, "brandname": "BMW", "modelname": "320i", "price": 258000}


def test_extract_power_from_engine_text():
    assert _extract_power_from_engine_text("1.4T 150HP L4") == 150
    assert _extract_power_from_engine_text("2.0T 252 hp L4") == 252
    assert _extract_power_from_engine_text("нет мощности") is None


def test_normalize_transmission_codes():
    assert _normalize_che168_transmission("7") == "7-speed"
    assert _normalize_che168_transmission("6") == "6-speed"
    assert _normalize_che168_transmission("1-speed DHT") == "1-speed DHT"


def test_normalize_drive_canonical():
    assert _normalize_che168_drive("Front-Wheel Drive (FWD)") == "FWD"
    assert _normalize_che168_drive("Rear-Wheel Drive") == "RWD"
    assert _normalize_che168_drive("前置四驱") == "前置四驱"


def test_year_from_yearname_fallback():
    assert _year_from_yearname("2022.06", None) == 2022
    assert _year_from_yearname(None, 2019) == 2019


def test_parse_one_uses_engine_power_first():
    car = parse_one_che168_car_sync(
        external_id="58097504",
        list_item={"id": 58097504, "brandname": "BMW", "modelname": "320i", "price": 258000},
        carinfo={
            "title": "BMW 320i",
            "price": 258000,
            "engine": "1.4T 150HP L4",
            "images": ["https://erscglobal2.autoimg.cn/escimg/auto/x.jpg.webp"],
            "vin": "WBA12345678901234",
            "specid": 46482,
        },
        specparam={"displacement": "2.0T", "gearbox": "AT", "fueltype": "Gasoline"},
        specconfig={"list": [{"name": "Sunroof"}]},
        recommend=None,
        report_summary=None,
        assume_price_wan_yuan=False,
    )
    assert car is not None
    assert car["data"].get("power_hp") == 150
    assert car["data"].get("engine") == "1.4T 150HP L4"


def test_parse_one_year_from_yearname_when_year_missing():
    car = parse_one_che168_car_sync(
        external_id="58097505",
        list_item={"id": 58097505, "brandname": "Test", "price": 200000},
        carinfo={
            "title": "Test",
            "price": 200000,
            "brandname": "Test",
            "yearname": "2022.06",
            "specid": 1,
        },
        specparam=None,
        specconfig=None,
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    assert car["data"].get("year") == 2022
    assert car["data"].get("yearname") == "2022.06"


def test_parse_one_gearbox_numeric_code_normalized():
    car = parse_one_che168_car_sync(
        external_id="58097506",
        list_item={"id": 58097506, "brandname": "VW", "price": 180000},
        carinfo={"title": "VW", "price": 180000, "brandname": "VW", "specid": 2},
        specparam={"result": {"gearbox": "7"}},
        specconfig=None,
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    assert car["data"].get("transmission_type") == "7-speed"


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


def test_parse_one_collects_images_from_catepiclist():
    car = parse_one_che168_car_sync(
        external_id="555",
        list_item={"id": 555, "brandname": "BMW", "modelname": "X3", "price": 200000},
        carinfo={
            "title": "Catepiclist gallery",
            "price": 200000,
            "catepiclist": [
                {
                    "title": "外观",
                    "list": [
                        "https://erscglobal2.autoimg.cn/escimg/auto/a.jpg.webp",
                        "https://erscglobal2.autoimg.cn/escimg/auto/b.jpg.webp",
                    ],
                },
                {
                    "title": "内饰",
                    "list": [
                        "https://erscglobal2.autoimg.cn/escimg/auto/c.jpg.webp",
                    ],
                },
            ],
            # cover должен оставаться в начале (prepend_cover=True на первом источнике)
            "picurl": "https://erscglobal2.autoimg.cn/escimg/auto/cover.jpg.webp",
        },
        specparam=None,
        specconfig=None,
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    imgs = car["data"].get("images") or []
    assert len(imgs) >= 4
    assert imgs[0].endswith("cover.jpg.webp")
    assert any(u.endswith("a.jpg.webp") for u in imgs)
    assert any(u.endswith("c.jpg.webp") for u in imgs)


def test_merge_carinfo_envelope_keeps_sibling_images():
    raw = {
        "returncode": 0,
        "result": {
            "infoid": 777,
            "title": "Sibling images test",
            "price": 200000,
            "brandname": "BMW",
            "modelname": "X3",
        },
        "images": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
    }
    merged = merge_che168_api_carinfo_envelope(raw)
    assert merged.get("brandname") == "BMW"
    assert isinstance(merged.get("images"), list)
    assert len(merged["images"]) == 2
    car = parse_one_che168_car_sync(
        external_id="777",
        list_item={"id": 777, "price": 200000},
        carinfo=merged,
        specparam=None,
        specconfig=None,
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    assert len(car["data"].get("images") or []) >= 2


def test_extract_gallery_urls_from_detail_html():
    html = (
        "props:[\"https://erscglobal2.autoimg.cn/escimg/auto/a.jpg.webp\","
        "\"https://erscglobal2.autoimg.cn/escimg/auto/b.jpg.webp\"]"
    )
    u = extract_gallery_urls_from_detail_html(html)
    assert len(u) == 2


def test_merge_che168_image_url_lists_dedupe():
    a = ["https://erscglobal2.autoimg.cn/a.webp", "https://erscglobal2.autoimg.cn/b.webp"]
    b = ["https://erscglobal2.autoimg.cn/a.webp", "https://erscglobal2.autoimg.cn/c.webp"]
    assert merge_che168_image_url_lists(a, b) == [
        "https://erscglobal2.autoimg.cn/a.webp",
        "https://erscglobal2.autoimg.cn/b.webp",
        "https://erscglobal2.autoimg.cn/c.webp",
    ]


def test_merge_carinfo_envelope_deep_nested_autoimg_urls():
    raw = {
        "returncode": 0,
        "result": {
            "infoid": 88,
            "title": "Deep pics",
            "price": 100000,
            "brandname": "B",
            "picurl": "https://erscglobal2.autoimg.cn/escimg/auto/cover.webp",
        },
        "sidecar": {
            "nodes": [
                {"x": "https://erscglobal2.autoimg.cn/escimg/auto/p1.webp"},
                "https://erscglobal2.autoimg.cn/escimg/auto/p2.webp",
            ]
        },
        "dealer_social": {"whatsapp": "https://wa.me/8612345678"},
    }
    merged = merge_che168_api_carinfo_envelope(raw)
    imgs = merged.get("images") or []
    assert len(imgs) >= 3
    assert all("wa.me" not in u for u in imgs)


def test_parse_one_collects_nested_images_and_shape_fallbacks():
    car = parse_one_che168_car_sync(
        external_id="100",
        list_item={
            "id": 100,
            "data": {"gallery": [{"image_url": "https://example.com/2.jpg"}]},
            "price": 240000,
            "brandname": "Audi",
        },
        carinfo={
            "price": 240000,
            "result": {
                "cover_image": "https://example.com/1.jpg",
                "detail": {"imglist": [{"bigUrl": "https://example.com/3.jpg"}]},
                "modelYear": 2021,
                "km": 55000,
            },
        },
        specparam={"result": {"gearBoxType": "AT", "engineType": "Gasoline"}},
        specconfig=None,
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    d = car["data"]
    assert len(d.get("images") or []) >= 3
    assert d.get("year") == 2021
    assert d.get("km_age") == 55000
    assert d.get("transmission_type") == "AT"
    assert d.get("engine_type") == "Gasoline"
    dq = d.get("data_quality") or {}
    assert (dq.get("field_sources") or {}).get("images")


def test_parse_one_extracts_spec_fields_from_nested_name_value_payload():
    car = parse_one_che168_car_sync(
        external_id="58123456",
        list_item={"id": 58123456, "brandname": "Audi", "modelname": "A4", "price": 228000},
        carinfo={"title": "Audi A4", "price": 228000, "specid": 70001},
        specparam={
            "result": {
                "paramtypeitems": [
                    {
                        "name": "发动机",
                        "paramitems": [
                            {"name": "排量(L)", "value": "2.0T"},
                            {"name": "最大马力(Ps)", "value": "190"},
                            {"name": "燃料形式", "value": "汽油"},
                        ],
                    },
                    {
                        "name": "底盘转向",
                        "paramitems": [
                            {"name": "驱动方式", "value": "前置前驱"},
                            {"name": "变速箱", "value": "7挡湿式双离合"},
                        ],
                    },
                    {
                        "name": "车身",
                        "paramitems": [{"name": "车身结构", "value": "4门5座三厢车"}],
                    },
                ]
            }
        },
        specconfig=None,
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    d = car["data"]
    assert d.get("power_hp") == 190
    assert d.get("displacement_cc") == 2000
    assert d.get("engine_type") == "汽油"
    assert d.get("transmission_type") == "7挡湿式双离合"
    assert d.get("drive_type") == "前置前驱"
    assert d.get("body_type") == "4门5座三厢车"


def test_parse_one_extracts_nested_specconfig_options():
    car = parse_one_che168_car_sync(
        external_id="58129999",
        list_item={"id": 58129999, "brandname": "Audi", "modelname": "A4", "price": 228000},
        carinfo={"title": "Audi A4", "price": 228000, "specid": 70002},
        specparam=None,
        specconfig={
            "result": {
                "configlist": [
                    {
                        "name": "外部配置",
                        "sublist": [
                            {
                                "name": "天窗",
                                "valueitems": [
                                    {"name": "可开启全景天窗", "value": "标配"},
                                    {"name": "电动天窗", "value": "选配"},
                                ],
                            }
                        ],
                    }
                ]
            }
        },
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    opts = car["data"].get("che168_recommended_options") or []
    assert "可开启全景天窗" in opts
    assert "电动天窗" in opts


def test_parse_one_extracts_options_from_unknown_nested_keys():
    car = parse_one_che168_car_sync(
        external_id="58120001",
        list_item={"id": 58120001, "brandname": "Audi", "modelname": "A4", "price": 228000},
        carinfo={"title": "Audi A4", "price": 228000, "specid": 70003},
        specparam={
            "result": {
                "meta": {
                    "rows": [
                        {"label": "驱动类型", "value": "前置四驱"},
                        {"label": "车身形式", "value": "SUV"},
                        {"label": "发动机", "value": "汽油"},
                    ]
                }
            }
        },
        specconfig={
            "payload": {
                "sections": [
                    {
                        "children": [
                            {"optionName": "HUD 抬头显示", "optionValue": "标配"},
                            {"optionName": "前排手机无线充电", "optionValue": "标配"},
                        ]
                    }
                ]
            }
        },
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    d = car["data"]
    assert d.get("drive_type") == "前置四驱"
    assert d.get("body_type") == "SUV"
    assert d.get("engine_type") == "汽油"
    opts = d.get("che168_recommended_options") or []
    assert "HUD 抬头显示" in opts
    assert "前排手机无线充电" in opts


def test_parse_one_extracts_english_paramtypeitems_format():
    car = parse_one_che168_car_sync(
        external_id="58120002",
        list_item={"id": 58120002, "brandname": "BYD", "modelname": "Song Plus", "price": 168000},
        carinfo={"title": "BYD Song Plus", "price": 168000, "specid": 70004},
        specparam={
            "result": {
                "paramtypeitems": [
                    {
                        "name": "Basic Specifications",
                        "paramitems": [
                            {"name": "Engine Displacement", "value": "1.5L"},
                            {"name": "Max Power (hp)", "value": "112"},
                            {"name": "Transmission", "value": "1-speed DHT"},
                            {"name": "Drive Mode", "value": "Front-Wheel Drive (FWD)"},
                            {"name": "Energy Type", "value": "Plug-in Hybrid"},
                            {"name": "Body Structure", "value": "SUV"},
                        ],
                    }
                ]
            }
        },
        specconfig={
            "result": {
                "list": [
                    {"name": "Safety", "list": ["ABS", "ESP", "Airbags"]},
                    {"name": "Comfort", "list": ["Climate control", "Cruise control"]},
                ]
            }
        },
        recommend=None,
        report_summary=None,
    )
    assert car is not None
    d = car["data"]
    assert d.get("power_hp") == 112
    assert d.get("displacement_cc") == 1500
    assert d.get("engine_type") == "Plug-in Hybrid"
    assert d.get("transmission_type") == "1-speed DHT"
    assert d.get("drive_type") == "FWD"
    assert d.get("body_type") == "SUV"
    opts = d.get("che168_recommended_options") or []
    assert "ABS" in opts
    assert "ESP" in opts
    assert any("круиз" in str(x).lower() for x in opts) or "Cruise control" in opts


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
