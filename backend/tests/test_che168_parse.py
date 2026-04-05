"""Che168 HTML parsing and normalization."""

from __future__ import annotations

from che168.normalize import card_li_attrs_to_payload, listing_to_car_payload, parse_card_text
from che168.parse import anchor_text_by_pairs, find_dealer_pairs, parse_cards_li_rows
from che168.urls import build_list_page_url


def test_find_dealer_pairs_unique_order():
    html = """
    <a href="https://www.che168.com/dealer/1/10.html">A</a>
    <a href="/dealer/2/20.html">B</a>
    <a href='https://che168.com/dealer/1/10.html'>dup</a>
    """
    assert find_dealer_pairs(html) == [("1", "10"), ("2", "20")]


def test_anchor_text_by_pairs():
    html = '<a href="/dealer/5/99.html?x=1"><span>云车展6.7万公里</span></a>'
    assert anchor_text_by_pairs(html).get(("5", "99")) == "云车展6.7万公里"


def test_parse_card_text_mileage_year_price():
    t = "云车展6.7万公里／2021-08／成都／会员8.78万25.88万"
    d = parse_card_text(t)
    assert d.get("km_age") == 67000
    assert d.get("year") == "2021"
    assert d.get("yearMonth") == "202108"
    assert abs(d.get("price_cny", 0) - 87800.0) < 0.01


def test_parse_cards_li_rows_from_tag():
    html = (
        '<li class="cards-li list-photo-li" infoid="55353538" carname="宝马X5" price="16.98" '
        'cid="110100" pid="110000" milage="8.3" regdate="2015/09" specid="20751" dealerid="604572">'
    )
    rows = parse_cards_li_rows(html)
    assert len(rows) == 1
    assert rows[0]["infoid"] == "55353538"
    assert rows[0]["dealerid"] == "604572"
    assert rows[0]["price"] == "16.98"


def test_card_li_attrs_to_payload_price_km():
    attrs = {
        "infoid": "55353538",
        "dealerid": "604572",
        "carname": "宝马X5",
        "price": "16.98",
        "milage": "8.3",
        "regdate": "2015/09",
        "specid": "20751",
    }
    p = card_li_attrs_to_payload(attrs, cny_to_rub=10.0)
    d = p["data"]
    assert d["my_price"] == 1698000  # 16.98万 * 10000 * 10
    assert d["km_age"] == 83000
    assert d["year"] == "2015"


def test_build_list_page_url():
    assert "china/list/" in build_list_page_url(page=2)
    assert "page=2" in build_list_page_url(page=2)
    assert "/china/dazhong/" in build_list_page_url(brand_slug="dazhong", page=1)
    assert "/china/dazhong/sagitar/" in build_list_page_url(brand_slug="dazhong", series_slug="sagitar", page=3)


def test_listing_payload_car_id_shape():
    p = listing_to_car_payload("563148", "58018664", anchor_text="8.78万", cny_to_rub=10.0)
    assert "data" in p
    assert p["data"]["source"] == "che168"
    assert p["data"]["inner_id"] == "58018664"
    assert p["data"]["my_price"] == 878000  # 8.78万 * 10000 * 10
