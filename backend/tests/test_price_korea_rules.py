from __future__ import annotations

from pricekorea import (
    KOREA_PRICING_RULES_VERSION,
    PriceCalculatorKorea,
    korea_json_suggests_pricing_resync,
    sync_korea_pricing_clean_block,
)


def test_sync_korea_pricing_clean_block_sets_version() -> None:
    data = {"source": "encar", "pricing_tier": "full_customs", "my_price": 1_500_000.0}
    sync_korea_pricing_clean_block(data)
    pc = data.get("pricing_clean") or {}
    assert pc["pricing_rules_version"] == KOREA_PRICING_RULES_VERSION
    assert pc["pricing_tier"] == "full_customs"
    assert pc["final_price_rub"] == 1_500_000.0


def test_korea_json_suggests_pricing_resync_for_stale_version() -> None:
    data = {
        "source": "encar",
        "price_won": 20000000,
        "pricing_clean": {"pricing_rules_version": "legacy"},
    }
    assert korea_json_suggests_pricing_resync(data) is True


def test_korea_json_suggests_pricing_resync_false_for_current_version() -> None:
    data = {
        "source": "encar",
        "price_won": 20000000,
        "pricing_clean": {"pricing_rules_version": KOREA_PRICING_RULES_VERSION},
    }
    assert korea_json_suggests_pricing_resync(data) is False


def test_korea_nested_config_overrides_constants() -> None:
    calc = PriceCalculatorKorea(config_path="config.json")
    calc._fx.config = {
        "price": {
            "korea": {
                "documents_krw": 123000,
                "freight_usd": 777,
                "broker_rub": 55555,
            }
        }
    }
    cfg = calc._get_price_config()
    assert cfg["documents_krw"] == 123000
    assert cfg["freight_usd"] == 777
    assert cfg["broker_rub"] == 55555


def test_korea_fx_cache_reuses_first_snapshot() -> None:
    calc = PriceCalculatorKorea(config_path="config.json")
    calc._fx.config = {"price": {"cache_minutes": 10}}
    calls = {"krw": 0, "usd": 0, "eur": 0}

    def _krw():
        calls["krw"] += 1
        return 0.07, "mock"

    def _usd():
        calls["usd"] += 1
        return 100.0

    def _eur():
        calls["eur"] += 1
        return 110.0

    calc._fx.resolve_korea_krw_to_rub = _krw  # type: ignore[method-assign]
    calc._fx.get_cbr_usd_rub_exclusive = _usd  # type: ignore[method-assign]
    calc._fx.get_cbr_eur_rub_safe = _eur  # type: ignore[method-assign]
    car = {"price_won": 2500, "year": 2020, "displacement": 2000}
    calc.calculate_total_cost(car)
    calc.calculate_total_cost(car)
    assert calls["krw"] == 1
    assert calls["usd"] == 1
    assert calls["eur"] == 1
