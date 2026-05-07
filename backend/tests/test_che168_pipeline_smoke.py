from __future__ import annotations

from scraper_pipeline.che168.api_outcome import che168_carinfo_outcome
from scraper_pipeline.che168.parser import (
    merge_che168_api_carinfo_envelope,
    parse_one_che168_car_sync,
)


def test_che168_pipeline_smoke_carinfo_to_parsed_card() -> None:
    raw_carinfo = {
        "returncode": 0,
        "result": {
            "infoid": 7001,
            "title": "Smoke BMW X3",
            "price": 238000,
            "brandname": "BMW",
            "modelname": "X3",
            "catepiclist": [
                {
                    "title": "外观",
                    "list": [
                        "https://erscglobal2.autoimg.cn/escimg/auto/a.jpg.webp",
                        "https://erscglobal2.autoimg.cn/escimg/auto/b.jpg.webp",
                    ],
                }
            ],
            "specid": 46481,
        },
        "images": ["https://erscglobal2.autoimg.cn/escimg/auto/c.jpg.webp"],
    }

    assert che168_carinfo_outcome(200, raw_carinfo) == "ok"
    ci_body = merge_che168_api_carinfo_envelope(raw_carinfo)
    car = parse_one_che168_car_sync(
        external_id="7001",
        list_item={"id": 7001, "price": 238000, "brandname": "BMW", "modelname": "X3"},
        carinfo=ci_body,
        specparam={"result": {"gearbox": "AT", "fueltype": "Gasoline"}},
        specconfig={"list": [{"name": "Sunroof"}]},
        recommend={"result": {"list": [{"id": "7002"}]}},
        report_summary=None,
        assume_price_wan_yuan=False,
    )
    assert car is not None
    d = car["data"]
    assert d["id"] == "che168-7001"
    assert d["price_cny"] == 238000.0
    assert d["mark"] == "BMW"
    assert d["model"] == "X3"
    assert (d.get("images") or []) and len(d["images"]) >= 2
    assert d.get("che168_similar_listing_ids") == ["7002"]
