#!/usr/bin/env python3
"""Аудит контракта парсера Che168 в PostgreSQL (аналог encar_parser_audit для China)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from parser_audit_common import (  # noqa: E402
    audit_append_history,
    audit_pct,
    audit_print_section,
    audit_read_last_summary_from_history,
    audit_trim_history_file,
)
from pricechina import CHINA_PRICING_RULES_VERSION  # noqa: E402
from slack_ops import notify_slack_alert  # noqa: E402


def _postgres_dsn(config_path: Path) -> str:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml and config_path.is_file():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            dsn = str((((cfg.get("storage") or {}).get("postgres") or {}).get("dsn") or "")).strip())
            if dsn:
                return dsn
        except Exception:
            pass
    return (os.environ.get("DATABASE_URL") or "").strip()


def _delta(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    t, pt = int(current.get("total") or 0), int(previous.get("total") or 0)
    m, pm = int(current.get("with_missing_required") or 0), int(previous.get("with_missing_required") or 0)
    c, pc = int(current.get("with_contract_violations") or 0), int(previous.get("with_contract_violations") or 0)
    return {
        "delta_total": t - pt,
        "delta_pct_missing_required": round(audit_pct(m, t) - audit_pct(pm, pt), 2),
        "delta_pct_contract_violations": round(audit_pct(c, t) - audit_pct(pc, pt), 2),
    }


def _evaluate(
    summary: dict[str, Any],
    delta: dict[str, Any],
    *,
    max_missing_pct: float,
    max_contract_pct: float,
    min_schema_pct: float,
    max_missing_delta: float,
    max_contract_delta: float,
) -> list[str]:
    fail: list[str] = []
    pm = float(summary.get("pct_missing_required") or 0.0)
    pc = float(summary.get("pct_contract_violations") or 0.0)
    ps = float(summary.get("pct_schema_version") or 0.0)
    if max_missing_pct >= 0 and pm > max_missing_pct:
        fail.append(f"pct_missing_required={pm:.2f}% > {max_missing_pct:.2f}%")
    if max_contract_pct >= 0 and pc > max_contract_pct:
        fail.append(f"pct_contract_violations={pc:.2f}% > {max_contract_pct:.2f}%")
    if min_schema_pct >= 0 and ps < min_schema_pct:
        fail.append(f"pct_schema_version={ps:.2f}% < {min_schema_pct:.2f}%")
    if delta and max_missing_delta >= 0:
        d = float(delta.get("delta_pct_missing_required") or 0.0)
        if d > max_missing_delta:
            fail.append(f"delta_pct_missing_required={d:.2f} > {max_missing_delta:.2f}")
    if delta and max_contract_delta >= 0:
        d = float(delta.get("delta_pct_contract_violations") or 0.0)
        if d > max_contract_delta:
            fail.append(f"delta_pct_contract_violations={d:.2f} > {max_contract_delta:.2f}")
    return fail


def run(
    *,
    dsn: str,
    limit: int,
    history_file: str,
    baseline_json: str,
    fail_on_regression: bool,
    max_missing_pct: float,
    max_contract_pct: float,
    min_schema_pct: float,
    max_missing_delta: float,
    max_contract_delta: float,
    slack_webhook_url: str,
    slack_bot_token: str,
    slack_channel_id: str,
    keep_history_days: int,
) -> int:
    baseline: dict[str, Any] = {}
    if baseline_json:
        try:
            baseline = json.loads(baseline_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid baseline JSON: {exc}") from exc
    elif history_file:
        baseline = audit_read_last_summary_from_history(history_file)

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM cars
                WHERE lower(trim(source)) = 'che168'
                """
            )
            total = int(cur.fetchone()[0] or 0)
            print(f"Che168 rows: {total}")

            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE data ? 'parser_schema_version') AS with_schema_version,
                  COUNT(*) FILTER (
                    WHERE COALESCE(jsonb_array_length(data->'data_quality'->'missing_required_fields'), 0) > 0
                  ) AS with_missing_required,
                  COUNT(*) FILTER (
                    WHERE data ? 'data_quality'
                      AND jsonb_typeof(data->'data_quality'->'contract_violations') = 'object'
                      AND (data->'data_quality'->'contract_violations') <> '{}'::jsonb
                  ) AS with_contract_violations,
                  COUNT(*) FILTER (WHERE data ? 'raw_envelope') AS with_raw_envelope,
                  AVG(NULLIF(data->'data_quality'->>'raw_coverage_pct', '')::float) AS avg_raw_coverage_pct,
                  AVG(NULLIF(data->'data_quality'->>'raw_quality_score', '')::float) AS avg_raw_quality_score,
                  COUNT(*) FILTER (
                    WHERE NULLIF((data->>'price_cny')::text, '') IS NOT NULL
                      AND (data->>'price_cny')::numeric > 0
                  ) AS priced_cnt,
                  COUNT(*) FILTER (WHERE COALESCE((data->>'price_on_request')::boolean, false)) AS por_cnt,
                  COUNT(*) FILTER (WHERE COALESCE(data->>'che168_listing_cluster_id', '') <> '') AS with_cluster,
                  COUNT(*) FILTER (
                    WHERE COALESCE(data->'pricing_clean'->>'pricing_rules_version', '') = %s
                  ) AS china_rules_current
                FROM cars
                WHERE lower(trim(source)) = 'che168'
                """,
                (CHINA_PRICING_RULES_VERSION,),
            )
            row = cur.fetchone()
            with_schema = int(row[0] or 0)
            with_missing = int(row[1] or 0)
            with_contract = int(row[2] or 0)
            with_raw = int(row[3] or 0)
            avg_cov = round(float(row[4] or 0.0), 2)
            avg_q = round(float(row[5] or 0.0), 2)
            priced = int(row[6] or 0)
            por = int(row[7] or 0)
            with_cluster = int(row[8] or 0)
            china_rules_ok = int(row[9] or 0)

            cur.execute(
                """
                SELECT data->>'che168_listing_cluster_method' AS method, COUNT(*) AS cnt
                FROM cars
                WHERE lower(trim(source)) = 'che168'
                  AND COALESCE(data->>'che168_listing_cluster_method', '') <> ''
                GROUP BY 1
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (limit,),
            )
            audit_print_section("Cluster method distribution", cur.fetchall())

            cur.execute(
                """
                SELECT reason, COUNT(*) AS cnt
                FROM cars c
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    COALESCE(c.data->'data_quality'->'reasons', '[]'::jsonb)
                ) AS reason
                WHERE lower(trim(c.source)) = 'che168'
                GROUP BY reason
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (limit,),
            )
            audit_print_section("Top data_quality reasons", cur.fetchall())

            cur.execute(
                """
                SELECT k AS contract_group, COUNT(*) AS cnt
                FROM cars c
                CROSS JOIN LATERAL jsonb_object_keys(
                    COALESCE(c.data->'data_quality'->'contract_violations', '{}'::jsonb)
                ) AS k
                WHERE lower(trim(c.source)) = 'che168'
                GROUP BY k
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (limit,),
            )
            audit_print_section("Contract violation groups", cur.fetchall())

            summary = {
                "total": total,
                "with_schema_version": with_schema,
                "with_missing_required": with_missing,
                "with_contract_violations": with_contract,
                "with_raw_envelope": with_raw,
                "priced_cnt": priced,
                "por_cnt": por,
                "with_cluster": with_cluster,
                "china_pricing_rules_current": china_rules_ok,
                "pct_schema_version": audit_pct(with_schema, total),
                "pct_missing_required": audit_pct(with_missing, total),
                "pct_contract_violations": audit_pct(with_contract, total),
                "pct_raw_envelope": audit_pct(with_raw, total),
                "pct_priced": audit_pct(priced, total),
                "pct_china_pricing_rules_current": audit_pct(china_rules_ok, total),
                "avg_raw_coverage_pct": avg_cov,
                "avg_raw_quality_score": avg_q,
                "china_pricing_rules_version_expected": CHINA_PRICING_RULES_VERSION,
            }
            print("\n## Summary JSON")
            print(json.dumps(summary, ensure_ascii=False))

            delta: dict[str, Any] = {}
            if baseline:
                delta = _delta(summary, baseline)
                print("\n## Delta vs baseline")
                print(json.dumps(delta, ensure_ascii=False))

            if history_file:
                audit_append_history(history_file, summary, delta)
                audit_trim_history_file(history_file, keep_history_days)
                print(f"\n## History: {history_file}")

            failures = _evaluate(
                summary,
                delta,
                max_missing_pct=max_missing_pct,
                max_contract_pct=max_contract_pct,
                min_schema_pct=min_schema_pct,
                max_missing_delta=max_missing_delta,
                max_contract_delta=max_contract_delta,
            )
            if failures:
                print("\n## Regression: FAIL")
                for f in failures:
                    print(f" - {f}")
            else:
                print("\n## Regression: PASS")

            slack_lines = [
                f"*Che168 parser audit* — {'FAIL' if failures else 'PASS'}",
                f"rows={total} schema={summary['pct_schema_version']}% "
                f"missing={summary['pct_missing_required']}% "
                f"contract_viol={summary['pct_contract_violations']}% "
                f"raw_env={summary['pct_raw_envelope']}% "
                f"china_rules_ok={summary['pct_china_pricing_rules_current']}%",
            ]
            if failures:
                slack_lines.extend(["", *failures])
            notify_slack_alert(
                "\n".join(slack_lines),
                webhook_url=slack_webhook_url,
                bot_token=slack_bot_token,
                channel_id=slack_channel_id,
            )
            if fail_on_regression and failures:
                return 2
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit Che168 parser fields in PostgreSQL")
    ap.add_argument("--config", default="", help="YAML with storage.postgres.dsn (optional if DATABASE_URL)")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--baseline-json", default="")
    ap.add_argument(
        "--history-file",
        default=str(_BACKEND_DIR / "data" / "che168_parser_audit_history.jsonl"),
    )
    ap.add_argument("--fail-on-regression", action="store_true")
    ap.add_argument("--max-missing-required-pct", type=float, default=-1.0)
    ap.add_argument("--max-contract-violations-pct", type=float, default=-1.0)
    ap.add_argument("--min-schema-coverage-pct", type=float, default=-1.0)
    ap.add_argument("--max-missing-delta-pct", type=float, default=-1.0)
    ap.add_argument("--max-contract-delta-pct", type=float, default=-1.0)
    ap.add_argument("--keep-history-days", type=int, default=7)
    ap.add_argument("--slack-webhook-url", default=(os.environ.get("CHE168_PARSER_AUDIT_SLACK_WEBHOOK") or "").strip())
    ap.add_argument("--slack-bot-token", default=(os.environ.get("OPS_SLACK_BOT_TOKEN") or "").strip())
    ap.add_argument("--slack-channel-id", default=(os.environ.get("OPS_SLACK_CHANNEL_ID") or "").strip())
    args = ap.parse_args()

    dsn = _postgres_dsn(Path(args.config).expanduser().resolve()) if args.config else (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise SystemExit("Need DATABASE_URL or --config with storage.postgres.dsn")

    rc = run(
        dsn=dsn,
        limit=max(1, args.limit),
        history_file=(args.history_file or "").strip(),
        baseline_json=(args.baseline_json or "").strip(),
        fail_on_regression=bool(args.fail_on_regression),
        max_missing_pct=float(args.max_missing_required_pct),
        max_contract_pct=float(args.max_contract_violations_pct),
        min_schema_pct=float(args.min_schema_coverage_pct),
        max_missing_delta=float(args.max_missing_delta_pct),
        max_contract_delta=float(args.max_contract_delta_pct),
        slack_webhook_url=(args.slack_webhook_url or "").strip(),
        slack_bot_token=(args.slack_bot_token or "").strip(),
        slack_channel_id=(args.slack_channel_id or "").strip(),
        keep_history_days=max(0, int(args.keep_history_days)),
    )
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
