#!/usr/bin/env python3
"""Catalog Pipeline lag metrics: PG active rows vs Meili docs → textfile for Prometheus.

Env:
  DATABASE_URL / WRA_PG_DSN / SYNC_PG_DSN
  WRA_MEILISEARCH_URL, MEILI_MASTER_KEY / WRA_MEILISEARCH_KEY
  WRA_MEILI_LIVE_INDEX (default cars)
  WRA_CATALOG_LAG_TEXTFILE — path to *.prom
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


def _env(*keys: str) -> str:
    for k in keys:
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    return ""


def _pg_active_count(dsn: str) -> Optional[int]:
    try:
        import psycopg2
    except ImportError:
        print("catalog_pipeline_lag_metrics: psycopg2 missing", file=sys.stderr)
        return None
    try:
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                # Active = not linked away as duplicate; sold flags stay in index policy separately.
                cur.execute(
                    """
                    SELECT COUNT(*) FROM cars
                    WHERE dedupe_canonical_car_id IS NULL
                    """
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0
        finally:
            conn.close()
    except Exception as e:
        print(f"catalog_pipeline_lag_metrics: pg error: {e}", file=sys.stderr)
        return None


def _meili_stats(url: str, key: str, index: str) -> Optional[dict[str, Any]]:
    endpoint = url.rstrip("/") + f"/indexes/{index}/stats"
    req = urllib.request.Request(endpoint)
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"catalog_pipeline_lag_metrics: meili error: {e}", file=sys.stderr)
        return None


def main() -> int:
    path = _env("WRA_CATALOG_LAG_TEXTFILE")
    if not path:
        return 0
    dsn = _env("DATABASE_URL", "SYNC_PG_DSN", "WRA_PG_DSN")
    meili_url = _env("WRA_MEILISEARCH_URL") or "http://127.0.0.1:7700"
    meili_key = _env("MEILI_MASTER_KEY", "WRA_MEILISEARCH_KEY")
    index = _env("WRA_MEILI_LIVE_INDEX", "WRA_MEILISEARCH_INDEX") or "cars"

    pg_n = _pg_active_count(dsn) if dsn else None
    stats = _meili_stats(meili_url, meili_key, index)
    meili_n: Optional[int] = None
    if isinstance(stats, dict):
        for k in ("numberOfDocuments", "number_of_documents"):
            if k in stats:
                try:
                    meili_n = int(stats[k])
                except (TypeError, ValueError):
                    pass
                break

    lines = [
        "# HELP wra_catalog_pg_active_rows Cars rows eligible for Meili (no dedupe link)",
        "# TYPE wra_catalog_pg_active_rows gauge",
        f"wra_catalog_pg_active_rows {pg_n if pg_n is not None else -1}",
        "# HELP wra_catalog_meili_documents Live Meilisearch document count",
        "# TYPE wra_catalog_meili_documents gauge",
        f"wra_catalog_meili_documents {meili_n if meili_n is not None else -1}",
    ]
    if pg_n is not None and meili_n is not None and pg_n >= 0:
        ratio = (float(meili_n) / float(pg_n)) if pg_n else 0.0
        lines += [
            "# HELP wra_catalog_meili_pg_ratio Meili docs / PG active rows",
            "# TYPE wra_catalog_meili_pg_ratio gauge",
            f"wra_catalog_meili_pg_ratio {ratio:.6f}",
            "# HELP wra_catalog_index_empty 1 if live Meili has zero documents",
            "# TYPE wra_catalog_index_empty gauge",
            f"wra_catalog_index_empty {1 if meili_n == 0 else 0}",
        ]
    lines.append("")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(out)
    print(
        f"catalog_lag: pg_active={pg_n} meili_docs={meili_n} index={index!r} -> {path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
