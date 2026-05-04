from pricechina import CHINA_PRICING_RULES_VERSION, china_json_suggests_pricing_resync


def test_china_resync_when_rules_stale():
    d = {
        "source": "che168",
        "price_cny": 100_000,
        "pricing_clean": {"pricing_rules_version": "legacy"},
    }
    assert china_json_suggests_pricing_resync(d) is True


def test_china_no_resync_when_current():
    d = {
        "source": "che168",
        "price_cny": 100_000,
        "pricing_clean": {"pricing_rules_version": CHINA_PRICING_RULES_VERSION},
    }
    assert china_json_suggests_pricing_resync(d) is False


def test_china_no_resync_without_source_price():
    d = {"source": "che168", "pricing_clean": {}}
    assert china_json_suggests_pricing_resync(d) is False


def test_encar_not_china_heuristic():
    d = {
        "source": "encar",
        "price_cny": 50000,
        "pricing_clean": {"pricing_rules_version": "x"},
    }
    assert china_json_suggests_pricing_resync(d) is False
