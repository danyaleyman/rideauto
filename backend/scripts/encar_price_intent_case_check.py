#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import requests

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from encar_price_intent import PriceIntent, classify_encar_price_intent


def _postgres_dsn(config_path: Path) -> str:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml and config_path.is_file():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            dsn = str((((cfg.get("storage") or {}).get("postgres") or {}).get("dsn") or "")).strip()
            if dsn:
                return dsn
        except Exception:
            pass
    return (os.environ.get("DATABASE_URL") or "").strip()


def _parse_case_arg(raw: str) -> Tuple[str, str]:
    s = str(raw or "").strip()
    if "=" not in s:
        raise ValueError(f"invalid --case format: {raw!r}; expected car_id=intent")
    car_id, expected = s.split("=", 1)
    car_id = car_id.strip()
    expected = expected.strip()
    allowed = {"sale", "monthly_finance", "reserved_placeholder", "unknown"}
    if not car_id:
        raise ValueError(f"empty car_id in case: {raw!r}")
    if expected not in allowed:
        raise ValueError(f"invalid expected intent {expected!r}; allowed={sorted(allowed)}")
    return car_id, expected


def _load_cases(cases_file: str, case_args: Sequence[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for c in case_args:
        car_id, expected = _parse_case_arg(c)
        out.append({"car_id": car_id, "expected_intent": expected, "source": "cli"})
    if cases_file:
        p = Path(cases_file)
        if not p.is_file():
            raise FileNotFoundError(f"cases file not found: {cases_file}")
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("cases file must be JSON array")
        for row in raw:
            if not isinstance(row, dict):
                continue
            car_id = str(row.get("car_id") or "").strip()
            expected = str(row.get("expected_intent") or "").strip()
            if not car_id or not expected:
                continue
            _, expected = _parse_case_arg(f"{car_id}={expected}")
            out.append(
                {
                    "car_id": car_id,
                    "expected_intent": expected,
                    "source": "file",
                    "note": str(row.get("note") or "").strip(),
                }
            )
    # dedupe by car_id, keep last
    dedup: Dict[str, Dict[str, str]] = {}
    for row in out:
        dedup[row["car_id"]] = row
    return list(dedup.values())


def _fetch_rows_by_car_ids(dsn: str, car_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    import psycopg2
    import psycopg2.extras

    q = """
    SELECT car_id, data
    FROM cars
    WHERE source='encar'
      AND car_id = ANY(%s)
    """
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, (list(car_ids),))
            out: Dict[str, Dict[str, Any]] = {}
            for row in cur.fetchall():
                car_id = str(row.get("car_id") or "").strip()
                data = row.get("data")
                if not car_id or not isinstance(data, dict):
                    continue
                out[car_id] = data
            return out


def _fetch_detail_html(car_id: str, timeout_sec: float) -> str:
    url = f"https://fem.encar.com/cars/detail/{car_id}?carid={car_id}"
    r = requests.get(
        url,
        timeout=timeout_sec,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; WRA-CaseCheck/1.0)",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        },
    )
    if r.status_code != 200:
        return ""
    return r.text or ""


def run_case_check(
    dsn: str,
    *,
    cases: Sequence[Dict[str, str]],
    timeout_sec: float,
    delay_min: float,
    delay_max: float,
    use_live_html: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rows = _fetch_rows_by_car_ids(dsn, [c["car_id"] for c in cases])
    results: List[Dict[str, Any]] = []
    stats = {"total": 0, "pass": 0, "fail": 0, "missing_db": 0}
    for c in cases:
        car_id = c["car_id"]
        expected = c["expected_intent"]
        payload = rows.get(car_id)
        if not payload:
            stats["total"] += 1
            stats["fail"] += 1
            stats["missing_db"] += 1
            results.append(
                {
                    "car_id": car_id,
                    "expected": expected,
                    "actual": "missing_db",
                    "ok": False,
                    "signals": [],
                }
            )
            continue
        html = _fetch_detail_html(car_id, timeout_sec=timeout_sec) if use_live_html else ""
        actual, signals = classify_encar_price_intent(payload, extra_texts=[html] if html else None)
        ok = actual == expected
        stats["total"] += 1
        stats["pass" if ok else "fail"] += 1
        results.append(
            {
                "car_id": car_id,
                "expected": expected,
                "actual": actual,
                "ok": ok,
                "signals": signals,
                "note": c.get("note", ""),
            }
        )
        time.sleep(random.uniform(delay_min, delay_max))
    return results, stats


def main() -> None:
    p = argparse.ArgumentParser(description="Check Encar price_intent on fixed car cases")
    p.add_argument("--config", default="scraper_config.yaml")
    p.add_argument("--cases-file", default="", help="JSON array: [{car_id, expected_intent, note}]")
    p.add_argument("--case", action="append", default=[], help="Inline case: car_id=intent")
    p.add_argument("--timeout-sec", type=float, default=10.0)
    p.add_argument("--delay-min", type=float, default=0.1)
    p.add_argument("--delay-max", type=float, default=0.4)
    p.add_argument("--no-live-html", action="store_true", help="Do not fetch live Encar HTML")
    args = p.parse_args()

    dsn = _postgres_dsn(Path(args.config).expanduser().resolve())
    if not dsn:
        raise SystemExit("DATABASE_URL/storage.postgres.dsn is empty")
    cases = _load_cases(args.cases_file, args.case or [])
    if not cases:
        raise SystemExit("No cases provided. Use --case car_id=intent or --cases-file")

    results, stats = run_case_check(
        dsn,
        cases=cases,
        timeout_sec=max(2.0, min(args.timeout_sec, 30.0)),
        delay_min=max(0.0, args.delay_min),
        delay_max=max(max(0.0, args.delay_min), args.delay_max),
        use_live_html=not bool(args.no_live_html),
    )
    print(json.dumps({"stats": stats, "results": results}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if stats["fail"] == 0 else 2)


if __name__ == "__main__":
    main()

