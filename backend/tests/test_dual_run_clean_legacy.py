from __future__ import annotations

from dual_run_clean_legacy import aggregate_dual_run_stats, diff_read_model_fields, dual_run_should_fail


def test_diff_read_model_fields_equal() -> None:
    a = {"mark": "Kia", "price_rub": 1.0}
    assert diff_read_model_fields(a, dict(a)) == []


def test_diff_read_model_fields_detects() -> None:
    legacy = {"mark": "A", "price_rub": 100.0}
    clean = {"mark": "B", "price_rub": 100.0}
    d = diff_read_model_fields(legacy, clean)
    assert d == ["mark"]


def test_semantic_mode_ignores_mark_model() -> None:
    legacy = {
        "mark": "Kia",
        "model": "K5",
        "engine_type": "Бензин",
        "price_rub": 100.0,
        "pricing_tier": "korea_land_only",
        "price_on_request": False,
        "reserved_placeholder": False,
        "customs_included": False,
        "insurance_cases": 0,
        "damaged_parts_count": 0,
        "drive_type": "",
        "power_hp": None,
    }
    clean = dict(legacy)
    clean["mark"] = "기아"
    clean["engine_type"] = "가솔린"
    stats_full, _ = aggregate_dual_run_stats([("1", legacy, clean)], semantic=False)
    assert stats_full["rows_with_any_diff"] == 1
    stats_sem, _ = aggregate_dual_run_stats([("1", legacy, clean)], semantic=True)
    assert stats_sem["rows_with_any_diff"] == 0
    assert stats_sem["compare_mode"] == "semantic"


def test_aggregate_and_fail_threshold() -> None:
    rows = [
        ("1", {"a": 1}, {"a": 1}),
        ("2", {"a": 1}, {"a": 2}),
        ("3", {"a": 1}, {"a": 1}),
    ]
    stats, sample = aggregate_dual_run_stats(rows)
    assert stats["checked"] == 3
    assert stats["rows_with_any_diff"] == 1
    assert round(stats["pct_rows_with_any_diff"], 2) == 33.33
    assert "a" in stats["by_field"]
    assert len(sample) == 1

    fail, _ = dual_run_should_fail(stats, max_row_diff_pct=50.0)
    assert fail is False
    fail2, msg = dual_run_should_fail(stats, max_row_diff_pct=30.0)
    assert fail2 is True
    assert "pct_rows_with_any_diff" in msg
