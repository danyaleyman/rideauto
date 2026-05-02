from hp_catalog_quality import secondary_review_hint


def test_secondary_review_hints_gray_zones():
    assert secondary_review_hint(displacement_cc=2000, power_hp=440, engine_type="Gasoline") == "high_hp_per_liter_gray_zone"
    assert secondary_review_hint(displacement_cc=3100, power_hp=210, engine_type="Diesel") == "large_displacement_low_hp_gray_zone"


def test_secondary_review_skips_ev():
    assert secondary_review_hint(displacement_cc=None, power_hp=221, engine_type="Electric") is None
