from __future__ import annotations

from market_pricing_shared import VAT_IMPORT_RATE, excise_rub, vat_import_rub


def test_excise_progressive_hp_180():
    # 0–90: 0; 90–150: 64×60; 150–180: 613×30
    assert excise_rub(180.0) == 60.0 * 64.0 + 30.0 * 613.0


def test_excise_flat_zero_first_bracket():
    assert excise_rub(90.0) == 0.0
    assert excise_rub(91.0) == 64.0


def test_vat_on_customs_base():
    base = 1_000_000.0 + 350_000.0 + 22_230.0
    assert vat_import_rub(1_000_000.0, 350_000.0, 22_230.0, fuel="ice", age_years=3) == round(
        base * VAT_IMPORT_RATE, 2
    )
