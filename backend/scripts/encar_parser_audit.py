from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from slack_ops import notify_slack_alert  # noqa: E402


def _dsn_from_env() -> str:
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    return dsn


def _print_section(title: str, rows: list[tuple[Any, ...]]) -> None:
    print(f"\n## {title}")
    if not rows:
        print("(empty)")
        return
    for row in rows:
        print(" - " + " | ".join("" if v is None else str(v) for v in row))


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _read_last_summary_from_history(history_file: str) -> dict[str, Any]:
    p = Path(history_file)
    if not p.is_file():
        return {}
    lines = p.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        summary = row.get("summary")
        if isinstance(summary, dict):
            return summary
    return {}


def _append_history(history_file: str, summary: dict[str, Any], delta: dict[str, Any]) -> None:
    p = Path(history_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "delta": delta,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _trim_history_file(history_file: str, keep_days: int) -> None:
    """Keep JSONL records whose `ts` is within the last keep_days (UTC)."""
    if keep_days <= 0:
        return
    p = Path(history_file)
    if not p.is_file():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    kept: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        ts_raw = row.get("ts")
        if not isinstance(ts_raw, str):
            kept.append(line)
            continue
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            kept.append(line)
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            kept.append(line)
    p.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")


def _delta(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    total = int(current.get("total") or 0)
    with_schema_version = int(current.get("with_schema_version") or 0)
    with_missing_required = int(current.get("with_missing_required") or 0)
    with_contract_violations = int(current.get("with_contract_violations") or 0)
    prev_total = int(previous.get("total") or 0)
    prev_schema = int(previous.get("with_schema_version") or 0)
    prev_missing = int(previous.get("with_missing_required") or 0)
    prev_contract_violations = int(previous.get("with_contract_violations") or 0)
    return {
        "delta_total": total - prev_total,
        "delta_with_schema_version": with_schema_version - prev_schema,
        "delta_with_missing_required": with_missing_required - prev_missing,
        "delta_with_contract_violations": with_contract_violations - prev_contract_violations,
        "delta_pct_schema_version": round(_pct(with_schema_version, total) - _pct(prev_schema, prev_total), 2),
        "delta_pct_missing_required": round(_pct(with_missing_required, total) - _pct(prev_missing, prev_total), 2),
        "delta_pct_contract_violations": round(
            _pct(with_contract_violations, total) - _pct(prev_contract_violations, prev_total),
            2,
        ),
        "delta_pct_sale": round(float(current.get("pct_sale") or 0.0) - float(previous.get("pct_sale") or 0.0), 2),
        "delta_pct_monthly_finance": round(float(current.get("pct_monthly_finance") or 0.0) - float(previous.get("pct_monthly_finance") or 0.0), 2),
        "delta_pct_reserved_placeholder": round(
            float(current.get("pct_reserved_placeholder") or 0.0)
            - float(previous.get("pct_reserved_placeholder") or 0.0),
            2,
        ),
    }


def _evaluate_regression(
    current_summary: dict[str, Any],
    delta: dict[str, Any],
    max_missing_required_pct: float,
    max_missing_required_delta_pct: float,
    min_schema_coverage_pct: float,
    max_monthly_share_delta_pct: float,
    max_reserved_share_delta_pct: float,
) -> list[str]:
    failures: list[str] = []
    pct_missing = float(current_summary.get("pct_missing_required") or 0.0)
    pct_schema = float(current_summary.get("pct_schema_version") or 0.0)
    delta_missing = float(delta.get("delta_pct_missing_required") or 0.0)
    delta_monthly = abs(float(delta.get("delta_pct_monthly_finance") or 0.0))
    delta_reserved = abs(float(delta.get("delta_pct_reserved_placeholder") or 0.0))
    if max_missing_required_pct >= 0 and pct_missing > max_missing_required_pct:
        failures.append(
            f"pct_missing_required={pct_missing:.2f}% > threshold={max_missing_required_pct:.2f}%"
        )
    if max_missing_required_delta_pct >= 0 and delta and delta_missing > max_missing_required_delta_pct:
        failures.append(
            f"delta_pct_missing_required={delta_missing:.2f}% > threshold={max_missing_required_delta_pct:.2f}%"
        )
    if min_schema_coverage_pct >= 0 and pct_schema < min_schema_coverage_pct:
        failures.append(
            f"pct_schema_version={pct_schema:.2f}% < threshold={min_schema_coverage_pct:.2f}%"
        )
    if max_monthly_share_delta_pct >= 0 and delta and delta_monthly > max_monthly_share_delta_pct:
        failures.append(
            f"abs(delta_pct_monthly_finance)={delta_monthly:.2f}% > threshold={max_monthly_share_delta_pct:.2f}%"
        )
    if max_reserved_share_delta_pct >= 0 and delta and delta_reserved > max_reserved_share_delta_pct:
        failures.append(
            f"abs(delta_pct_reserved_placeholder)={delta_reserved:.2f}% > threshold={max_reserved_share_delta_pct:.2f}%"
        )
    return failures


def _failure_hint_ru(failure_line: str) -> str:
    if "pct_missing_required" in failure_line and "threshold" in failure_line:
        return "Доля строк с непустым списком missing_required в data_quality."
    if "delta_pct_missing_required" in failure_line:
        return "Скачок доли missing_required относительно прошлого запуска."
    if "pct_schema_version" in failure_line and "threshold" in failure_line:
        return "Доля строк, где в JSON есть parser_schema_version."
    if "pct_schema_version" in failure_line:
        return "Покрытие полем parser_schema_version."
    if "delta_pct_monthly_finance" in failure_line:
        return "Изменение доли объявлений с intent monthly_finance."
    if "delta_pct_reserved_placeholder" in failure_line:
        return "Изменение доли объявлений с intent reserved_placeholder."
    return "Подробности см. в stdout / journalctl этого запуска."


def format_slack_audit_report(
    *,
    slack_channel_label: str,
    current_summary: dict[str, Any],
    delta: dict[str, Any],
    failures: list[str],
    history_file: str,
) -> str:
    """Человекочитаемый текст для Slack (без сырого JSON)."""
    ok = not failures
    status_ru = "успешно завершён" if ok else "остановлен с ошибками регрессии"
    bar = "══════════════════════════════════════"
    lines: list[str] = [
        bar,
        f"Encar parser audit — {'OK' if ok else 'FAILED'}",
        bar,
        "",
        f"Итог: прогон {status_ru}.",
        "",
        "Где смотреть",
        "• Скрипт: backend/scripts/encar_parser_audit.py",
        "• Данные: PostgreSQL, таблица cars, фильтр source = encar",
        "",
        "Сводка по текущей выборке",
        f"• Всего строк Encar: {int(current_summary.get('total') or 0)}",
        f"• С parser_schema_version в data: {int(current_summary.get('with_schema_version') or 0)} "
        f"({float(current_summary.get('pct_schema_version') or 0):.2f}%)",
        f"• С missing_required (data_quality): {int(current_summary.get('with_missing_required') or 0)} "
        f"({float(current_summary.get('pct_missing_required') or 0):.2f}%)",
        f"• С нарушениями контракта (contract_violations): {int(current_summary.get('with_contract_violations') or 0)} "
        f"({float(current_summary.get('pct_contract_violations') or 0):.2f}%)",
        f"• Intent sale / monthly / reserved: "
        f"{float(current_summary.get('pct_sale') or 0):.2f}% / "
        f"{float(current_summary.get('pct_monthly_finance') or 0):.2f}% / "
        f"{float(current_summary.get('pct_reserved_placeholder') or 0):.2f}%",
        f"• Средний raw_quality_score: {float(current_summary.get('avg_raw_quality_score') or 0):.2f}",
        f"• С clean_schema_version: {int(current_summary.get('with_clean_schema') or 0)} "
        f"({float(current_summary.get('pct_with_clean_schema') or 0):.2f}%)",
    ]
    if slack_channel_label:
        lines.extend(["", f"Метка окружения (текст): {slack_channel_label}"])

    if delta:
        lines.extend(
            [
                "",
                "Дельта к прошлому запуску (history file)",
                f"• Строк Encar: {int(delta.get('delta_total') or 0):+d}",
                f"• Покрытие schema_version (п.п.): {float(delta.get('delta_pct_schema_version') or 0):+.2f}",
                f"• Покрытие missing_required (п.п.): {float(delta.get('delta_pct_missing_required') or 0):+.2f}",
                f"• Доля monthly_finance (п.п.): {float(delta.get('delta_pct_monthly_finance') or 0):+.2f}",
                f"• Доля reserved_placeholder (п.п.): {float(delta.get('delta_pct_reserved_placeholder') or 0):+.2f}",
            ]
        )
    else:
        lines.extend(["", "Дельта к прошлому запуску: нет базы (первый прогон или пустой history file)."])

    if failures:
        lines.extend(["", "Раздел: регресс по порогам", "Нарушены условия из параметров запуска (--max-*, --min-*):", ""])
        for msg in failures:
            lines.append(f"• {msg}")
            lines.append(f"  → {_failure_hint_ru(msg)}")
    else:
        lines.extend(["", "Раздел: регресс по порогам", "• Нарушений нет."])

    if history_file:
        lines.extend(["", f"Файл истории (JSONL): {history_file}"])

    lines.extend(["", "Полный вывод и при необходимости JSON — в логе запуска (stdout / journalctl)."])
    return "\n".join(lines)


def run(
    limit: int,
    baseline_json: str = "",
    history_file: str = "",
    fail_on_regression: bool = False,
    max_missing_required_pct: float = -1.0,
    max_missing_required_delta_pct: float = -1.0,
    min_schema_coverage_pct: float = -1.0,
    max_monthly_share_delta_pct: float = -1.0,
    max_reserved_share_delta_pct: float = -1.0,
    slack_webhook_url: str = "",
    slack_bot_token: str = "",
    slack_channel_id: str = "",
    slack_channel: str = "",
    keep_history_days: int = 0,
) -> int:
    dsn = _dsn_from_env()
    baseline = {}
    if baseline_json:
        try:
            baseline = json.loads(baseline_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid --baseline-json: {exc}") from exc
    elif history_file:
        baseline = _read_last_summary_from_history(history_file)
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM cars
                WHERE source = 'encar'
                """
            )
            total = int(cur.fetchone()[0] or 0)
            print(f"enCar rows: {total}")

            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE data ? 'parser_schema_version') AS with_schema_version,
                  COUNT(*) FILTER (
                    WHERE COALESCE(jsonb_array_length(data->'data_quality'->'missing_required_fields'), 0) > 0
                  ) AS with_missing_required,
                  COUNT(*) FILTER (WHERE (data->>'insurance_cases')::int > 0) AS with_insurance_cases,
                  COUNT(*) FILTER (WHERE (data->>'damaged_parts_count')::int > 0) AS with_damage_parts,
                  COUNT(*) FILTER (WHERE COALESCE(data->>'price_intent', '') = 'sale') AS sale_cnt,
                  COUNT(*) FILTER (WHERE COALESCE(data->>'price_intent', '') = 'monthly_finance') AS monthly_cnt,
                  COUNT(*) FILTER (WHERE COALESCE(data->>'price_intent', '') = 'reserved_placeholder') AS reserved_cnt,
                  COUNT(*) FILTER (
                    WHERE data ? 'data_quality'
                      AND jsonb_typeof(data->'data_quality'->'contract_violations') = 'object'
                      AND (data->'data_quality'->'contract_violations') <> '{}'::jsonb
                  ) AS with_contract_violations,
                  AVG(NULLIF(data->'data_quality'->>'raw_quality_score', '')::float) AS avg_raw_quality_score,
                  COUNT(*) FILTER (WHERE COALESCE(data->>'clean_schema_version', '') <> '') AS with_clean_schema
                FROM cars
                WHERE source = 'encar'
                """
            )
            summary = cur.fetchone()
            print(
                "schema/missing/insurance/damage:",
                json.dumps(
                    {
                        "with_schema_version": int(summary[0] or 0),
                        "with_missing_required": int(summary[1] or 0),
                        "with_insurance_cases": int(summary[2] or 0),
                        "with_damage_parts": int(summary[3] or 0),
                        "sale_cnt": int(summary[4] or 0),
                        "monthly_cnt": int(summary[5] or 0),
                        "reserved_cnt": int(summary[6] or 0),
                        "with_contract_violations": int(summary[7] or 0),
                        "avg_raw_quality_score": round(float(summary[8] or 0.0), 2),
                        "with_clean_schema": int(summary[9] or 0),
                    },
                    ensure_ascii=False,
                ),
            )
            with_schema_version = int(summary[0] or 0)
            with_missing_required = int(summary[1] or 0)
            sale_cnt = int(summary[4] or 0)
            monthly_cnt = int(summary[5] or 0)
            reserved_cnt = int(summary[6] or 0)
            with_contract_violations = int(summary[7] or 0)
            avg_raw_quality_score = round(float(summary[8] or 0.0), 2)
            with_clean_schema = int(summary[9] or 0)

            cur.execute(
                """
                SELECT
                  data->'parser_source_shapes_hash'->>'detail' AS detail_shape_hash,
                  COUNT(*) AS cnt
                FROM cars
                WHERE source = 'encar'
                GROUP BY 1
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (limit,),
            )
            _print_section("Top detail shape hashes", cur.fetchall())

            cur.execute(
                """
                SELECT
                  reason,
                  COUNT(*) AS cnt
                FROM cars c
                CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(c.data->'data_quality'->'reasons', '[]'::jsonb)) AS reason
                WHERE c.source = 'encar'
                GROUP BY reason
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (limit,),
            )
            _print_section("Top data_quality reasons", cur.fetchall())

            cur.execute(
                """
                SELECT
                  k AS contract_group,
                  COUNT(*) AS cnt
                FROM cars c
                CROSS JOIN LATERAL jsonb_object_keys(COALESCE(c.data->'data_quality'->'contract_violations', '{}'::jsonb)) AS k
                WHERE c.source = 'encar'
                GROUP BY k
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (limit,),
            )
            _print_section("Top raw-json contract violation groups", cur.fetchall())

            cur.execute(
                """
                SELECT
                  car_id,
                  data->'data_quality'->'missing_required_fields' AS missing,
                  data->>'url' AS url
                FROM cars
                WHERE source = 'encar'
                  AND COALESCE(jsonb_array_length(data->'data_quality'->'missing_required_fields'), 0) > 0
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            _print_section("Recent rows with missing required fields", cur.fetchall())

            current_summary = {
                "total": total,
                "with_schema_version": with_schema_version,
                "with_missing_required": with_missing_required,
                "pct_schema_version": _pct(with_schema_version, total),
                "pct_missing_required": _pct(with_missing_required, total),
                "sale_cnt": sale_cnt,
                "monthly_finance_cnt": monthly_cnt,
                "reserved_placeholder_cnt": reserved_cnt,
                "pct_sale": _pct(sale_cnt, total),
                "pct_monthly_finance": _pct(monthly_cnt, total),
                "pct_reserved_placeholder": _pct(reserved_cnt, total),
                "with_contract_violations": with_contract_violations,
                "pct_contract_violations": _pct(with_contract_violations, total),
                "avg_raw_quality_score": avg_raw_quality_score,
                "with_clean_schema": with_clean_schema,
                "pct_with_clean_schema": _pct(with_clean_schema, total),
            }
            print("\n## Summary JSON")
            print(json.dumps(current_summary, ensure_ascii=False))
            delta = {}
            if baseline:
                print("\n## Delta vs baseline")
                delta = _delta(current_summary, baseline)
                print(json.dumps(delta, ensure_ascii=False))
            if history_file:
                _append_history(history_file, current_summary, delta)
                _trim_history_file(history_file, keep_history_days)
                print(f"\n## History file\n{history_file}")
            failures = _evaluate_regression(
                current_summary=current_summary,
                delta=delta,
                max_missing_required_pct=max_missing_required_pct,
                max_missing_required_delta_pct=max_missing_required_delta_pct,
                min_schema_coverage_pct=min_schema_coverage_pct,
                max_monthly_share_delta_pct=max_monthly_share_delta_pct,
                max_reserved_share_delta_pct=max_reserved_share_delta_pct,
            )
            if failures:
                print("\n## Regression check: FAIL")
                for msg in failures:
                    print(f" - {msg}")
            else:
                print("\n## Regression check: PASS")
            slack_text = format_slack_audit_report(
                slack_channel_label=(slack_channel or "").strip(),
                current_summary=current_summary,
                delta=delta,
                failures=failures,
                history_file=(history_file or "").strip(),
            )
            notify_slack_alert(
                slack_text,
                webhook_url=slack_webhook_url,
                bot_token=slack_bot_token,
                channel_id=slack_channel_id,
            )
            if fail_on_regression and failures:
                return 2
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit Encar parser contract fields in PostgreSQL")
    ap.add_argument("--limit", type=int, default=20, help="max rows per section")
    ap.add_argument(
        "--baseline-json",
        type=str,
        default="",
        help="previous summary JSON from prior run to print delta",
    )
    ap.add_argument(
        "--history-file",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "data" / "encar_parser_audit_history.jsonl"),
        help="append current summary and compare with previous run from this file",
    )
    ap.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="exit with non-zero code when regression thresholds are violated",
    )
    ap.add_argument(
        "--max-missing-required-pct",
        type=float,
        default=-1.0,
        help="hard fail threshold for pct_missing_required (negative disables)",
    )
    ap.add_argument(
        "--max-missing-required-delta-pct",
        type=float,
        default=-1.0,
        help="hard fail threshold for delta_pct_missing_required (negative disables)",
    )
    ap.add_argument(
        "--min-schema-coverage-pct",
        type=float,
        default=-1.0,
        help="hard fail threshold for pct_schema_version minimum (negative disables)",
    )
    ap.add_argument(
        "--max-monthly-share-delta-pct",
        type=float,
        default=-1.0,
        help="hard fail threshold for absolute delta of monthly_finance share in percent points",
    )
    ap.add_argument(
        "--max-reserved-share-delta-pct",
        type=float,
        default=-1.0,
        help="hard fail threshold for absolute delta of reserved_placeholder share in percent points",
    )
    ap.add_argument(
        "--slack-webhook-url",
        type=str,
        default=(os.environ.get("PARSER_AUDIT_SLACK_WEBHOOK") or "").strip(),
        help="Slack incoming webhook URL for nightly status posting",
    )
    ap.add_argument(
        "--slack-bot-token",
        type=str,
        default=(
            (
                os.environ.get("OPS_SLACK_BOT_TOKEN")
                or os.environ.get("PARSER_AUDIT_SLACK_BOT_TOKEN")
                or os.environ.get("SLACK_BOT_TOKEN")
                or ""
            ).strip()
        ),
        help="Slack app Bot User OAuth token (xoxb-…) for chat.postMessage — см. api.slack.com/apps",
    )
    ap.add_argument(
        "--slack-channel-id",
        type=str,
        default=(
            (os.environ.get("OPS_SLACK_CHANNEL_ID") or os.environ.get("PARSER_AUDIT_SLACK_CHANNEL_ID") or "")
            .strip()
        ),
        help="Slack channel id (C… / G…) куда бот пишет сообщения",
    )
    ap.add_argument(
        "--slack-channel",
        type=str,
        default=(os.environ.get("PARSER_AUDIT_SLACK_CHANNEL") or "").strip(),
        help="не ID канала: короткая метка в тексте сообщения (удобно при webhook)",
    )
    ap.add_argument(
        "--keep-history-days",
        type=int,
        default=7,
        help="trim JSONL history to this many days (0 = never trim)",
    )
    args = ap.parse_args()
    exit_code = run(
        limit=max(1, args.limit),
        baseline_json=args.baseline_json,
        history_file=(args.history_file or "").strip(),
        fail_on_regression=bool(args.fail_on_regression),
        max_missing_required_pct=float(args.max_missing_required_pct),
        max_missing_required_delta_pct=float(args.max_missing_required_delta_pct),
        min_schema_coverage_pct=float(args.min_schema_coverage_pct),
        max_monthly_share_delta_pct=float(args.max_monthly_share_delta_pct),
        max_reserved_share_delta_pct=float(args.max_reserved_share_delta_pct),
        slack_webhook_url=(args.slack_webhook_url or "").strip(),
        slack_bot_token=(args.slack_bot_token or "").strip(),
        slack_channel_id=(args.slack_channel_id or "").strip(),
        slack_channel=(args.slack_channel or "").strip(),
        keep_history_days=max(0, int(args.keep_history_days)),
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
