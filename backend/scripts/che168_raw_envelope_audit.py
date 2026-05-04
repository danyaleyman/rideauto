#!/usr/bin/env python3
"""Агрегаты по raw_envelope в cars.data для Che168 (глубина сырья / офлайн-аудит)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def _dsn(config_path: Path) -> str:
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


def main() -> int:
    import psycopg2
    import psycopg2.extras

    p = argparse.ArgumentParser(description="Che168 raw_envelope coverage audit (Postgres)")
    p.add_argument("--config", default="", help="YAML with storage.postgres.dsn")
    p.add_argument("--limit", type=int, default=20000, help="Max rows scanned")
    args = p.parse_args()

    dsn = _dsn(Path(args.config).expanduser().resolve()) if args.config else (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        print("Need DATABASE_URL or --config with dsn", file=sys.stderr)
        return 2

    missing_src_counter: Counter[str] = Counter()
    coverage_samples: List[float] = []
    n_no_envelope = n_with = 0
    version_counter: Counter[str] = Counter()

    with psycopg2.connect(dsn) as conn:
        with conn.cursor(name="env_audit", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT data
                FROM cars
                WHERE lower(trim(source)) = 'che168'
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (max(1, int(args.limit)),),
            )
            for row in cur:
                d = row.get("data")
                if isinstance(d, str):
                    try:
                        d = json.loads(d)
                    except Exception:
                        continue
                if not isinstance(d, dict):
                    continue
                inner = d.get("data")
                card = inner if isinstance(inner, dict) else d
                if not isinstance(card, dict):
                    continue
                env = card.get("raw_envelope")
                if not isinstance(env, dict):
                    n_no_envelope += 1
                    continue
                n_with += 1
                v = str(env.get("raw_schema_version") or "")
                if v:
                    version_counter[v] += 1
                integ = env.get("integrity")
                if isinstance(integ, dict):
                    for m in integ.get("missing_sources") or []:
                        if m:
                            missing_src_counter[str(m)] += 1
                    try:
                        coverage_samples.append(float(integ.get("coverage_pct") or 0.0))
                    except (TypeError, ValueError):
                        pass

    n = n_with + n_no_envelope
    avg_cov = sum(coverage_samples) / len(coverage_samples) if coverage_samples else 0.0
    out: Dict[str, Any] = {
        "scanned_total": n,
        "with_raw_envelope": n_with,
        "without_raw_envelope": n_no_envelope,
        "raw_schema_versions": dict(version_counter),
        "missing_source_hits": dict(missing_src_counter.most_common(20)),
        "avg_raw_coverage_pct": round(avg_cov, 2),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
