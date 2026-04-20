from catalog_listing_price import (
    china_market_car,
    dongchedi_has_buyer_price,
    dongchedi_has_source_price,
    encar_has_list_price,
)


def test_encar_has_list_price_from_won():
    assert encar_has_list_price({"price_won": 1500}) is True


def test_encar_has_list_price_from_price_string():
    assert encar_has_list_price({"price": " 350 "}) is True


def test_encar_no_list_price():
    assert encar_has_list_price({"price_won": 0}) is False
    assert encar_has_list_price({}) is False


def test_china_market_car():
    assert china_market_car("dongchedi-1", {"source": "encar"}) is True
    assert china_market_car("x", {"source": "dongchedi"}) is True
    assert china_market_car("415", {"source": "encar"}) is False


def test_dongchedi_has_buyer_price():
    assert dongchedi_has_buyer_price({"my_price": 1.5}) is True
    assert dongchedi_has_buyer_price({"my_price": 0}) is False


def test_dongchedi_has_source_price():
    assert dongchedi_has_source_price({"price_cny": 50000}) is True
    assert dongchedi_has_source_price({"price_cny": "0"}) is False
