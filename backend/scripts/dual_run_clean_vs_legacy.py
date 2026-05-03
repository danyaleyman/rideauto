#!/usr/bin/env python3
"""Dual-run: read model legacy vs clean на выборке Encar (блок D rollout)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from dual_run_clean_legacy import (  # noqa: E402
    aggregate_dual_run_stats,
    dual_run_should_fail,
)
from read_models import build_catalog_read_model  # noqa: E402


def _dsn() -> str:
    for key in ("DATABASE_URL", "SYNC_PG_DSN", "WRA_PG_DSN"):
        dsn = (os.environ.get(key) or "").strip()
        if dsn:
            return dsn
    raise RuntimeError("Задайте DATABASE_URL или SYNC_PG_DSN (или WRA_PG_DSN)")


def run(limit: int, source: str, *, semantic: bool) -> dict[str, Any]:
    rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    src = (source or "encar").strip().lower()
    with psycopg2.connect(_dsn()) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT car_id, data
                FROM cars
                WHERE source = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (src, max(1, limit)),
            )
            for row in cur.fetchall():
                data = row.get("data") if isinstance(row.get("data"), dict) else {}
                car_id = str(row.get("car_id") or "")
                legacy = build_catalog_read_model(data, use_clean=False)
                clean = build_catalog_read_model(data, use_clean=True)
                rows.append((car_id, legacy, clean))
    stats, sample = aggregate_dual_run_stats(rows, semantic=semantic)
    return {"stats": stats, "sample": sample}


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Сравнение build_catalog_read_model(use_clean=False) vs True на выборке из Postgres",
    )
    ap.add_argument("--limit", type=int, default=500, help="сколько последних по updated_at строк взять")
    ap.add_argument("--source", type=str, default="encar", help="cars.source (по умолчанию encar)")
    ap.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="завершить с кодом 2, если есть расхождения (любые)",
    )
    ap.add_argument(
        "--max-row-diff-pct",
        type=float,
        default=-1.0,
        help="если >= 0: завершить с кодом 2, когда доля строк с любым отличием выше порога (0–100)",
    )
    ap.add_argument(
        "--semantic",
        action="store_true",
        help="сравнивать только цену/tier/флаги/привод/мощность — без mark/model/топлива/кузова/цвета "
        "(иначе шум из RU vs KO в clean-слое)",
    )
    ap.add_argument("--quiet", action="store_true", help="не печатать человекочитаемое резюме в stderr")
    args = ap.parse_args()

    payload = run(limit=int(args.limit), source=str(args.source), semantic=bool(args.semantic))
    stats = payload["stats"]

    if not args.quiet:
        print(
            "dual_run_clean_vs_legacy: "
            f"mode={stats.get('compare_mode', '?')} "
            f"checked={stats.get('checked')} "
            f"rows_with_any_diff={stats.get('rows_with_any_diff')} "
            f"({stats.get('pct_rows_with_any_diff')}%)",
            file=sys.stderr,
        )
        by_field = stats.get("by_field") or {}
        if by_field:
            top = sorted(by_field.items(), key=lambda x: -x[1])[:12]
            print("top field diffs (count): " + ", ".join(f"{k}={v}" for k, v in top), file=sys.stderr)

    print(json.dumps(payload, ensure_ascii=False))

    exit_code = 0
    if args.fail_on_diff and int(stats.get("rows_with_any_diff") or 0) > 0:
        exit_code = 2
    max_pct = float(args.max_row_diff_pct)
    if max_pct >= 0.0:
        bad, reason = dual_run_should_fail(stats, max_row_diff_pct=max_pct)
        if bad:
            if not args.quiet:
                print(f"dual_run: FAIL {reason}", file=sys.stderr)
            exit_code = 2
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
