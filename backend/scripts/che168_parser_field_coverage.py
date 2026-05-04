#!/usr/bin/env python3
"""
Доля заполненности «справочных» полей парсера Che168 (аналог глубины hp/spec без отдельного hp_catalog).
Сканирует JSON в cars.data и считает % non-empty по списку полей.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

_SCRIPTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPTS_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Согласовано с parse_one_che168_car_sync (после выбрасывания None).
_FIELD_KEYS: List[str] = [
    "mark",
    "model",
    "year",
    "price_cny",
    "km_age",
    "vin",
    "images",
    "engine_type",
    "transmission_type",
    "body_type",
    "power_hp",
    "displacement_cc",
    "che168_params_raw",
    "raw_envelope",
]


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


def _card(payload: Dict[str, Any]) -> Dict[str, Any]:
    inner = payload.get("data")
    return inner if isinstance(inner, dict) else payload


def _present(val: Any, key: str) -> bool:
    if val is None:
        return False
    if key == "images" and isinstance(val, list):
        return len(val) > 0
    if key == "che168_params_raw" and isinstance(val, dict):
        return len(val) > 0
    if key == "raw_envelope" and isinstance(val, dict):
        return len(val) > 0
    if isinstance(val, (int, float)):
        return key != "year" or int(val) > 0
    if isinstance(val, str):
        return bool(val.strip())
    return True


def main() -> int:
    import psycopg2
    import psycopg2.extras

    p = argparse.ArgumentParser(description="Che168 parser field coverage (Postgres)")
    p.add_argument("--config", default="", help="YAML with storage.postgres.dsn")
    p.add_argument("--limit", type=int, default=20000, help="Max rows scanned")
    args = p.parse_args()

    dsn = _dsn(Path(args.config).expanduser().resolve()) if args.config else (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        print("Need DATABASE_URL or --config with dsn", file=sys.stderr)
        return 2

    hits: Dict[str, int] = {k: 0 for k in _FIELD_KEYS}
    n = 0

    with psycopg2.connect(dsn) as conn:
        with conn.cursor(name="field_cov", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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
                card = _card(d)
                if not isinstance(card, dict):
                    continue
                n += 1
                for k in _FIELD_KEYS:
                    if _present(card.get(k), k):
                        hits[k] += 1

    pct: Dict[str, float] = {}
    for k in _FIELD_KEYS:
        pct[k] = round(100.0 * hits[k] / n, 2) if n else 0.0

    out: Dict[str, Any] = {
        "scanned_rows": n,
        "field_presence_counts": hits,
        "field_presence_pct": pct,
        "fields": list(_FIELD_KEYS),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
