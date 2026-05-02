from catalog_encar_pricing import encar_effective_payload_for_tier, encar_tier_for_pricing_snapshot


def test_effective_payload_fills_displacement_from_spec_clean():
    d = {
        "engine_type": "gasoline",
        "spec_clean": {"displacement_cc": "1598", "engine_type": "diesel"},
    }
    eff = encar_effective_payload_for_tier(d)
    assert eff.get("displacement_cc") == "1598"
    assert eff.get("engine_type") == "gasoline"


def test_tier_snapshot_ice_cc_no_hp_is_land_only():
    d = {
        "engine_type": "gasoline",
        "spec_clean": {"displacement_cc": "998"},
    }
    assert encar_tier_for_pricing_snapshot(d) == "korea_land_only"


def test_tier_snapshot_ice_hp_and_cc_full_customs():
    d = {"engine_type": "gasoline", "power_hp": 120, "displacement": 1600}
    assert encar_tier_for_pricing_snapshot(d) == "full_customs"
