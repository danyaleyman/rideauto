from catalog_listing_price import encar_reserved_placeholder_price


def test_reserved_placeholder_detects_repeated_digits():
    assert encar_reserved_placeholder_price({"price": "4444"})
    assert encar_reserved_placeholder_price({"price": "9999"})
    assert encar_reserved_placeholder_price({"price_won": 11110000})


def test_reserved_placeholder_detects_repeated_digits_with_trailing_zero():
    assert encar_reserved_placeholder_price({"price": "4440"})
    assert encar_reserved_placeholder_price({"price": "5550"})
    assert encar_reserved_placeholder_price({"price_won": 44400000})
    assert encar_reserved_placeholder_price({"price_won": 77700000})


def test_reserved_placeholder_ignores_regular_prices():
    assert not encar_reserved_placeholder_price({"price": "4380"})
    assert not encar_reserved_placeholder_price({"price_won": 43800000})
    assert not encar_reserved_placeholder_price({"price": "2150"})
from catalog_listing_price import (
    china_market_car,
    dongchedi_has_buyer_price,
    dongchedi_has_source_price,
    encar_has_list_price,
    encar_reserved_placeholder_price,
)


def test_encar_has_list_price_from_won():
    assert encar_has_list_price({"price_won": 1500}) is True


def test_encar_has_list_price_from_price_string():
    assert encar_has_list_price({"price": " 350 "}) is True


def test_encar_no_list_price():
    assert encar_has_list_price({"price_won": 0}) is False
    assert encar_has_list_price({}) is False


def test_encar_monthly_finance_price_is_not_list_price():
    assert encar_has_list_price({"price_won": 6200, "encar_monthly_finance_price": True}) is False


def test_encar_reserved_placeholder_price_is_not_list_price():
    assert encar_has_list_price({"price_won": 9999}) is False
    assert encar_has_list_price({"price": "4,444"}) is False


def test_encar_reserved_placeholder_detector():
    assert encar_reserved_placeholder_price({"price_won": 1111}) is True
    assert encar_reserved_placeholder_price({"price_won": 99990000}) is True
    assert encar_reserved_placeholder_price({"price_won": 55550000}) is True
    assert encar_reserved_placeholder_price({"price_won": 77770000}) is True
    assert encar_reserved_placeholder_price({"price_won": 111110000}) is True
    assert encar_reserved_placeholder_price({"price": "2,190"}) is False


def test_encar_monthly_finance_fallback_fields_are_not_list_price():
    assert encar_has_list_price({"price_won": 2190, "encar_month_lease_price": 24}) is False
    assert encar_has_list_price({"price_won": 2190, "encar_lease_type": "월렌트"}) is False
    assert encar_has_list_price({"price_won": 4320, "price_text": "월36만원 월렌트(12개월)"}) is False
    assert (
        encar_has_list_price(
            {
                "price_won": 4320000,
                "price_text": "월36만원 월렌트(12개월) 인수금 0만원 차량가격 432만원",
            }
        )
        is False
    )


def test_encar_monthly_finance_legacy_small_price_won_not_list_price():
    assert encar_has_list_price({"source": "encar", "price_won": 33, "price": 0}) is False


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
