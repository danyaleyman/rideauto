#!/usr/bin/env python3
"""Метрики hp_catalog для дашборда / алертов мониторинга."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from hp_catalog_store import DEFAULT_DB_PATH, connect, ensure_schema


def _gather(conn) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM hp_catalog").fetchone()[0]
    with_hp = conn.execute(
        "SELECT COUNT(*) FROM hp_catalog WHERE power_hp IS NOT NULL AND power_hp > 0",
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM hp_catalog WHERE (power_hp IS NULL OR power_hp <= 0) AND llm_status='pending'",
    ).fetchone()[0]
    no_data = conn.execute(
        "SELECT COUNT(*) FROM hp_catalog WHERE (power_hp IS NULL OR power_hp <= 0) AND llm_status='no_data'",
    ).fetchone()[0]
    errors = conn.execute(
        "SELECT COUNT(*) FROM hp_catalog WHERE (power_hp IS NULL OR power_hp <= 0) AND llm_status='error'",
    ).fetchone()[0]

    low_conf_legacy = conn.execute(
        """
        SELECT COUNT(*) FROM hp_catalog
        WHERE source = 'catalog' AND llm_status = 'done' AND llm_confidence IS NULL AND power_hp > 0
        """,
    ).fetchone()[0]

    review_flagged = conn.execute(
        "SELECT COUNT(*) FROM hp_catalog WHERE COALESCE(review_flag, 0) != 0 AND power_hp > 0",
    ).fetchone()[0]

    oldest_pending_age_days: Optional[float] = None
    oldest_row = conn.execute(
        """
        SELECT created_at FROM hp_catalog
        WHERE (power_hp IS NULL OR power_hp <= 0) AND llm_status='pending'
        ORDER BY created_at ASC LIMIT 1
        """
    ).fetchone()
    if oldest_row and oldest_row[0]:
        try:
            ts = datetime.fromisoformat(str(oldest_row[0]).replace("Z", "+00:00"))
            oldest_pending_age_days = max(
                0.0,
                (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0,
            )
        except ValueError:
            oldest_pending_age_days = None

    conflict_groups = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT norm_manufacturer, norm_model, norm_engine_type, COALESCE(displacement_cc, -1), year_month
            FROM hp_catalog
            WHERE power_hp IS NOT NULL AND power_hp > 0 AND llm_status='done'
            GROUP BY norm_manufacturer, norm_model, norm_engine_type, COALESCE(displacement_cc, -1), year_month
            HAVING COUNT(DISTINCT power_hp) > 1
        ) AS _conflict_agg
        """
    ).fetchone()[0]

    by_prompt_ver = conn.execute(
        """
        SELECT COALESCE(NULLIF(trim(llm_prompt_version), ''), '(empty)') AS pv, COUNT(*)
        FROM hp_catalog WHERE llm_status = 'done' AND source = 'catalog' AND power_hp > 0
        GROUP BY pv ORDER BY COUNT(*) DESC LIMIT 20
        """
    ).fetchall()

    no_data_recent = conn.execute(
        """
        SELECT COUNT(*) FROM hp_catalog WHERE llm_status = 'no_data'
          AND (llm_reason LIKE '%confidence%' OR llm_reason LIKE '%sanity%' OR llm_reason LIKE '%rejected%')
        """
    ).fetchone()[0]

    pct_hp = round(float(with_hp) / float(total) * 100.0, 4) if total else 0.0

    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "total_rows": total,
        "with_power_hp": with_hp,
        "with_hp_pct": pct_hp,
        "pending_llm": pending,
        "no_data": no_data,
        "no_data_likely_rejected": no_data_recent,
        "error_rows": errors,
        "legacy_done_catalog_null_confidence": low_conf_legacy,
        "review_flagged_with_hp": review_flagged,
        "conflict_trim_hp_groups": conflict_groups,
        "oldest_pending_age_days": oldest_pending_age_days,
        "llm_prompt_version_counts_top": [{"version": str(r[0]), "count": int(r[1])} for r in by_prompt_ver],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="hp_catalog метрики: консоль, JSON, экспорт Prometheus")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Путь к hp_catalog.db")
    p.add_argument("--json", action="store_true", help="Одна строка JSON в stdout")
    p.add_argument(
        "--prometheus-textfile",
        type=Path,
        default=None,
        help="Записать gauge-метрики в файл (совместимо с node_exporter textfile collector)",
    )
    p.add_argument(
        "--alert-exit-nonzero",
        action="store_true",
        help="Выход код 3 при срабатывании порогов ниже",
    )
    p.add_argument("--alert-pending-gt", type=int, default=0, help="Алерт если pending строго больше этого")
    p.add_argument(
        "--alert-oldest-pending-days-gt",
        type=float,
        default=0.0,
        help="Алерт если самый старый pending старее N дней (0 = отключено)",
    )
    args = p.parse_args()

    conn = connect(args.db)
    ensure_schema(conn)
    try:
        data = _gather(conn)
    finally:
        conn.close()

    alert = False
    if args.alert_pending_gt > 0 and int(data["pending_llm"]) > args.alert_pending_gt:
        alert = True
        data["alert_pending_queue"] = True
    oldest = data["oldest_pending_age_days"]
    if (
        args.alert_oldest_pending_days_gt > 0
        and oldest is not None
        and float(oldest) > args.alert_oldest_pending_days_gt
    ):
        alert = True
        data["alert_pending_stale"] = True

    if args.json:
        print(json.dumps(data, ensure_ascii=False), flush=True)
    else:
        print(f"db={args.db}", flush=True)
        for k, v in sorted(data.items()):
            if k != "llm_prompt_version_counts_top":
                print(f"{k}={v}", flush=True)
        rows = data.get("llm_prompt_version_counts_top")
        if rows:
            print("llm_prompt_version_counts_top:", flush=True)
            for r in rows:
                print(f"  {r['version']}: {r['count']}", flush=True)

    if args.prometheus_textfile:
        pf = Path(args.prometheus_textfile)
        pf.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# HELP hp_catalog_rows_total Rows in hp_catalog",
            "# TYPE hp_catalog_rows_total gauge",
            f"hp_catalog_rows_total {int(data['total_rows'])}",
            "# HELP hp_catalog_pending_llm Rows waiting for LLM",
            "# TYPE hp_catalog_pending_llm gauge",
            f"hp_catalog_pending_llm {int(data['pending_llm'])}",
            "# HELP hp_catalog_review_flagged Rows with secondary review hint",
            "# TYPE hp_catalog_review_flagged gauge",
            f"hp_catalog_review_flagged {int(data['review_flagged_with_hp'])}",
            "# HELP hp_catalog_conflict_trim_hp_groups Distinct trims with differing hp",
            "# TYPE hp_catalog_conflict_trim_hp_groups gauge",
            f"hp_catalog_conflict_trim_hp_groups {int(data['conflict_trim_hp_groups'])}",
        ]
        if data["oldest_pending_age_days"] is not None:
            lines.extend(
                [
                    "# HELP hp_catalog_oldest_pending_age_days Age of oldest pending row",
                    "# TYPE hp_catalog_oldest_pending_age_days gauge",
                    f"hp_catalog_oldest_pending_age_days {float(data['oldest_pending_age_days']):.4f}",
                ]
            )
        tmp = pf.with_suffix(pf.suffix + ".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(pf)

    if args.alert_exit_nonzero and alert:
        print("ALERT thresholds exceeded.", file=sys.stderr, flush=True)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
