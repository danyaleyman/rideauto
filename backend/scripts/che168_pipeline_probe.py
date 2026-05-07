#!/usr/bin/env python3
"""
Probe Che168 data flow quality on recent cars:
Postgres (cars.data with inner/top fallback) -> /api/car/{id}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


FIELDS = (
    "power_hp",
    "displacement_cc",
    "engine_type",
    "transmission_type",
    "drive_type",
    "body_type",
)


def _is_present(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    return True


def _api_extract(result: Dict[str, Any], field: str) -> Any:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    rm = result.get("read_model") if isinstance(result.get("read_model"), dict) else {}
    if field == "power_hp":
        return data.get("power_hp") if _is_present(data.get("power_hp")) else rm.get("power_hp")
    if field == "displacement_cc":
        return data.get("displacement_cc")
    if field == "engine_type":
        return data.get("engine_type") if _is_present(data.get("engine_type")) else rm.get("engine_type")
    if field == "transmission_type":
        return data.get("transmission_type") if _is_present(data.get("transmission_type")) else rm.get("transmission_type")
    if field == "drive_type":
        return data.get("drive_type") if _is_present(data.get("drive_type")) else rm.get("drive_type")
    if field == "body_type":
        return data.get("body_type") if _is_present(data.get("body_type")) else rm.get("body_type")
    return data.get(field)


def _fetch_api_car(api_base: str, car_id: str, timeout: float) -> Dict[str, Any]:
    enc = urllib.parse.quote(car_id, safe="")
    url = f"{api_base.rstrip('/')}/api/car/{enc}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(body)
    result = parsed.get("result")
    return result if isinstance(result, dict) else {}


def main() -> int:
    import psycopg2
    import psycopg2.extras

    p = argparse.ArgumentParser(description="Che168 DB->API probe for tech fields")
    p.add_argument("--limit", type=int, default=50, help="Recent Che168 cars to check")
    p.add_argument("--api-base", default="http://127.0.0.1:8080", help="API base URL")
    p.add_argument("--timeout-sec", type=float, default=8.0, help="Per-request timeout")
    args = p.parse_args()

    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        print("Need DATABASE_URL in env", file=sys.stderr)
        return 2

    rows: List[Dict[str, Any]] = []
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                  car_id,
                  COALESCE(data->'data'->>'power_hp',          data->>'power_hp')          AS power_hp,
                  COALESCE(data->'data'->>'displacement_cc',   data->>'displacement_cc')   AS displacement_cc,
                  COALESCE(data->'data'->>'engine_type',       data->>'engine_type')       AS engine_type,
                  COALESCE(data->'data'->>'transmission_type', data->>'transmission_type') AS transmission_type,
                  COALESCE(data->'data'->>'drive_type',        data->>'drive_type')        AS drive_type,
                  COALESCE(data->'data'->>'body_type',         data->>'body_type')         AS body_type
                FROM cars
                WHERE lower(trim(source))='che168' OR car_id LIKE 'che168-%%'
                ORDER BY updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (max(1, int(args.limit)),),
            )
            rows = list(cur.fetchall())

    if not rows:
        print(json.dumps({"checked": 0, "error": "no che168 rows"}, ensure_ascii=False, indent=2))
        return 0

    db_counts = {f: 0 for f in FIELDS}
    api_counts = {f: 0 for f in FIELDS}
    api_errors: List[Dict[str, str]] = []
    samples_missing: Dict[str, List[str]] = {f: [] for f in FIELDS}

    for r in rows:
        car_id = str(r.get("car_id") or "").strip()
        if not car_id:
            continue
        for f in FIELDS:
            if _is_present(r.get(f)):
                db_counts[f] += 1
            elif len(samples_missing[f]) < 8:
                samples_missing[f].append(car_id)

        try:
            res = _fetch_api_car(args.api_base, car_id, timeout=float(args.timeout_sec))
            for f in FIELDS:
                if _is_present(_api_extract(res, f)):
                    api_counts[f] += 1
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            if len(api_errors) < 20:
                api_errors.append({"car_id": car_id, "error": str(e)[:220]})

    total = len(rows)
    out = {
        "checked": total,
        "api_base": args.api_base,
        "db_present": {k: {"count": v, "pct": round(v * 100.0 / total, 2)} for k, v in db_counts.items()},
        "api_present": {k: {"count": v, "pct": round(v * 100.0 / total, 2)} for k, v in api_counts.items()},
        "api_errors_count": len(api_errors),
        "api_errors_sample": api_errors,
        "db_missing_samples": samples_missing,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

