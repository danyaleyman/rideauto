#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg2


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _dsn_from_env() -> str:
    """Как у deploy/scripts/run_meilisearch_sync_host.sh: SYNC_PG_DSN → DATABASE_URL → WRA_PG_DSN."""
    for key in ("SYNC_PG_DSN", "DATABASE_URL", "WRA_PG_DSN"):
        dsn = (os.environ.get(key) or "").strip()
        if dsn:
            return dsn
    raise RuntimeError(
        "Задайте DSN: SYNC_PG_DSN, DATABASE_URL или WRA_PG_DSN (например после source /etc/default/rideauto)"
    )


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def run(
    dsn: str,
    min_price_coverage_pct: float,
    min_brand_coverage_pct: float,
    min_model_coverage_pct: float,
) -> int:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0) AS with_price,
                  COUNT(*) FILTER (WHERE COALESCE(mark, '') <> '') AS with_brand,
                  COUNT(*) FILTER (WHERE COALESCE(model, '') <> '') AS with_model
                FROM cars
                WHERE source='encar'
                """
            )
            total, with_price, with_brand, with_model = [int(x or 0) for x in cur.fetchone()]
    summary: dict[str, Any] = {
        "total": total,
        "pct_price_coverage": _pct(with_price, total),
        "pct_brand_coverage": _pct(with_brand, total),
        "pct_model_coverage": _pct(with_model, total),
    }
    print(json.dumps(summary, ensure_ascii=False))
    failures = []
    if summary["pct_price_coverage"] < min_price_coverage_pct:
        failures.append("price_coverage_below_threshold")
    if summary["pct_brand_coverage"] < min_brand_coverage_pct:
        failures.append("brand_coverage_below_threshold")
    if summary["pct_model_coverage"] < min_model_coverage_pct:
        failures.append("model_coverage_below_threshold")
    if failures:
        print(json.dumps({"failures": failures}, ensure_ascii=False))
        return 2
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Preflight data-quality gates before Meili sync")
    ap.add_argument(
        "--dsn",
        metavar="POSTGRES_URL",
        help="DSN Postgres (иначе SYNC_PG_DSN / DATABASE_URL / WRA_PG_DSN из окружения)",
    )
    ap.add_argument(
        "--min-price-coverage-pct",
        type=float,
        default=_env_float("WRA_MEILI_PREFLIGHT_MIN_PRICE_COVERAGE_PCT", 97.0),
    )
    ap.add_argument(
        "--min-brand-coverage-pct",
        type=float,
        default=_env_float("WRA_MEILI_PREFLIGHT_MIN_BRAND_COVERAGE_PCT", 99.0),
    )
    ap.add_argument(
        "--min-model-coverage-pct",
        type=float,
        default=_env_float("WRA_MEILI_PREFLIGHT_MIN_MODEL_COVERAGE_PCT", 99.0),
    )
    args = ap.parse_args()
    dsn = (args.dsn or "").strip() or _dsn_from_env()
    raise SystemExit(
        run(
            dsn,
            min_price_coverage_pct=float(args.min_price_coverage_pct),
            min_brand_coverage_pct=float(args.min_brand_coverage_pct),
            min_model_coverage_pct=float(args.min_model_coverage_pct),
        )
    )


if __name__ == "__main__":
    main()

