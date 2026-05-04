from catalog_encar_pricing import PRICING_RULES_VERSION, encar_json_suggests_pricing_resync


def test_resync_when_pricing_rules_version_stale():
    d = {
        "source": "encar",
        "price_won": 20_000_000,
        "pricing_clean": {"pricing_tier": "full_customs", "pricing_rules_version": "legacy"},
    }
    assert encar_json_suggests_pricing_resync(d) is True


def test_resync_when_por_but_snapshot_is_full_customs():
    d = {
        "source": "encar",
        "price_won": 20_000_000,
        "engine_type": "gasoline",
        "power_hp": 100,
        "displacement": 2000,
        "pricing_clean": {"pricing_tier": "price_on_request", "pricing_rules_version": PRICING_RULES_VERSION},
    }
    assert encar_json_suggests_pricing_resync(d) is True


def test_no_resync_when_aligned_full_customs():
    d = {
        "source": "encar",
        "price_won": 20_000_000,
        "engine_type": "gasoline",
        "power_hp": 100,
        "displacement": 2000,
        "pricing_clean": {
            "pricing_tier": "full_customs",
            "pricing_rules_version": PRICING_RULES_VERSION,
        },
    }
    assert encar_json_suggests_pricing_resync(d) is False


def test_no_resync_che168():
    d = {
        "source": "che168",
        "price_won": 20_000_000,
        "pricing_clean": {"pricing_rules_version": "x"},
    }
    assert encar_json_suggests_pricing_resync(d) is False
