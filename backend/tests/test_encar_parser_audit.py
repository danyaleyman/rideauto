from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.encar_parser_audit import (
    _delta,
    _evaluate_regression,
    _trim_history_file,
    format_slack_audit_report,
)


def test_delta_computation() -> None:
    current = {"total": 100, "with_schema_version": 95, "with_missing_required": 2, "with_contract_violations": 3}
    prev = {"total": 80, "with_schema_version": 80, "with_missing_required": 1, "with_contract_violations": 1}
    d = _delta(current, prev)
    assert d["delta_total"] == 20
    assert d["delta_with_schema_version"] == 15
    assert d["delta_with_missing_required"] == 1
    assert d["delta_with_contract_violations"] == 2


def test_regression_thresholds_trigger() -> None:
    current = {"pct_missing_required": 4.5, "pct_schema_version": 90.0}
    delta = {
        "delta_pct_missing_required": 1.2,
        "delta_pct_monthly_finance": 3.0,
        "delta_pct_reserved_placeholder": -2.0,
    }
    failures = _evaluate_regression(
        current_summary=current,
        delta=delta,
        max_missing_required_pct=2.0,
        max_missing_required_delta_pct=0.5,
        min_schema_coverage_pct=95.0,
        max_monthly_share_delta_pct=1.0,
        max_reserved_share_delta_pct=1.0,
    )
    assert len(failures) == 5
    assert any("pct_missing_required" in x for x in failures)
    assert any("delta_pct_missing_required" in x for x in failures)
    assert any("pct_schema_version" in x for x in failures)
    assert any("delta_pct_monthly_finance" in x for x in failures)
    assert any("delta_pct_reserved_placeholder" in x for x in failures)


def test_slack_report_human_readable() -> None:
    summary = {
        "total": 100,
        "with_schema_version": 90,
        "with_missing_required": 2,
        "pct_schema_version": 90.0,
        "pct_missing_required": 2.0,
        "with_contract_violations": 0,
        "pct_contract_violations": 0.0,
        "sale_cnt": 80,
        "monthly_finance_cnt": 10,
        "reserved_placeholder_cnt": 10,
        "pct_sale": 80.0,
        "pct_monthly_finance": 10.0,
        "pct_reserved_placeholder": 10.0,
        "avg_raw_quality_score": 0.5,
        "with_clean_schema": 0,
        "pct_with_clean_schema": 0.0,
    }
    delta = {
        "delta_total": 5,
        "delta_pct_schema_version": 1.0,
        "delta_pct_missing_required": -0.5,
        "delta_pct_monthly_finance": 0.0,
        "delta_pct_reserved_placeholder": 0.0,
    }
    text_ok = format_slack_audit_report(
        slack_channel_label="staging",
        current_summary=summary,
        delta=delta,
        failures=[],
        history_file="/tmp/h.jsonl",
    )
    assert "Encar parser audit" in text_ok
    assert "OK" in text_ok
    assert "Где смотреть" in text_ok
    assert "регресс по порогам" in text_ok
    assert "Нарушений нет" in text_ok
    text_fail = format_slack_audit_report(
        slack_channel_label="",
        current_summary=summary,
        delta=delta,
        failures=["pct_schema_version=50.00% < threshold=95.00%"],
        history_file="",
    )
    assert "FAILED" in text_fail
    assert "Раздел: регресс по порогам" in text_fail


def test_trim_history_keeps_recent_rows(tmp_path: Path) -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    p = tmp_path / "h.jsonl"
    p.write_text(
        json.dumps({"ts": old, "summary": {"x": 1}}, ensure_ascii=False)
        + "\n"
        + json.dumps({"ts": recent, "summary": {"x": 2}}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    _trim_history_file(str(p), keep_days=7)
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["summary"]["x"] == 2
