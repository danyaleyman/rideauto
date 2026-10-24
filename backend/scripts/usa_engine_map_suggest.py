#!/usr/bin/env python3
"""
Рост HP-библиотеки США: кандидаты в data/us_engine_map.json из vPIC по карточкам без мощности.

Зачем: us_engine_map.json — это библиотека (make/model/cc/fuel/годы), а не разовая заливка
под текущие ~495 машин. Новые модели/годы подтягивает vPIC по VIN (интернет), а этот скрипт
кристаллизует подтверждённые VIN-наблюдения в офлайн-записи каталога. После добавления
записей в JSON мощность присваивается уже на ingest, без сети
(см. us_power.enrich_usa_power_at_ingest).

Примеры:
    python backend/scripts/usa_engine_map_suggest.py --dsn "$DATABASE_URL"
    python backend/scripts/usa_engine_map_suggest.py --dsn "$DATABASE_URL" --min-count 2 \
        --json-out data/us_engine_map_candidates.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # psycopg2 нужен только для чтения БД (на сервере есть в venv)
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover - локальный запуск/тесты без драйвера
    psycopg2 = None  # type: ignore[assignment]

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from us_power import (  # noqa: E402
    flush_vin_cache,
    lookup_vin_power,
    suggest_library_entries,
    usa_engine_cc,
)

DEFAULT_SOURCE = "autotrader"


def _dsn(args_dsn: str) -> str:
    return (args_dsn or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN") or "").strip()


def _select_batch(cur: Any, source: str, last_id: int, limit: int) -> list:
    params: List[Any] = [last_id]
    where_source = ""
    if source and source != "*":
        where_source = "AND source = %s"
        params.append(source)
    params.append(limit)
    cur.execute(
        f"""
        SELECT id, data, power_hp
        FROM cars
        WHERE id > %s
          {where_source}
          AND (power_hp IS NULL OR power_hp <= 0)
          AND COALESCE(data->>'vin', '') <> ''
        ORDER BY id ASC
        LIMIT %s
        """,
        tuple(params),
    )
    return cur.fetchall()


def _sample_from_row(payload: Dict[str, Any], info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Карточка + данные vPIC → наблюдение для suggest_library_entries (make/model/cc/fuel/year/hp)."""
    hp = info.get("hp")
    if not hp:
        return None
    cc = info.get("cc") or usa_engine_cc(payload)
    make = str(payload.get("mark") or info.get("make") or "").strip()
    model = str(payload.get("model") or info.get("model") or "").strip()
    if not make or not model or not cc:
        return None
    return {
        "make": make,
        "model": model,
        "cc": cc,
        "fuel": payload.get("engine_type") or info.get("fuel"),
        "year": info.get("year") or payload.get("year"),
        "hp": hp,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Suggest us_engine_map.json entries from vPIC VIN data")
    p.add_argument("--dsn", default="", help="PostgreSQL DSN (или DATABASE_URL/WRA_PG_DSN)")
    p.add_argument("--source", default=DEFAULT_SOURCE, help="cars.source filter ('*' = все)")
    p.add_argument("--batch-size", type=int, default=500, help="Размер батча чтения")
    p.add_argument("--max-rows", type=int, default=0, help="Ограничить число карточек (0 = все)")
    p.add_argument("--no-vin", action="store_true", help="Без сети: брать только файловый кеш vPIC")
    p.add_argument("--min-count", type=int, default=1, help="Минимум VIN-наблюдений для записи")
    p.add_argument("--json-out", default="", help="Куда сохранить кандидатов (JSON)")
    args = p.parse_args()

    if args.no_vin:
        os.environ["USA_VIN_POWER"] = "0"

    if psycopg2 is None:
        print("psycopg2 is required to read the catalog: pip install psycopg2-binary")
        return 2

    dsn = _dsn(args.dsn)
    if not dsn:
        print("PostgreSQL DSN is required: --dsn или DATABASE_URL/WRA_PG_DSN")
        return 2

    samples: List[Dict[str, Any]] = []
    uncovered: Dict[str, int] = {}
    scanned = vin_hits = 0
    last_id = 0

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            while True:
                if args.max_rows > 0 and scanned >= args.max_rows:
                    break
                limit = args.batch_size
                if args.max_rows > 0:
                    limit = min(limit, args.max_rows - scanned)
                rows = _select_batch(cur, args.source, last_id, limit)
                if not rows:
                    break
                for row in rows:
                    last_id = int(row["id"])
                    scanned += 1
                    payload = row["data"]
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except Exception:
                            continue
                    if not isinstance(payload, dict):
                        continue
                    vin = str(payload.get("vin") or "").strip()
                    info = lookup_vin_power(vin) if vin else None
                    sample = _sample_from_row(payload, info) if info else None
                    if sample is None:
                        key = f"{payload.get('mark') or '?'} {payload.get('model') or '?'}".strip()
                        uncovered[key] = uncovered.get(key, 0) + 1
                        continue
                    vin_hits += 1
                    samples.append(sample)
                print(f"progress scanned={scanned} vin_hits={vin_hits} last_id={last_id}", flush=True)
    finally:
        flush_vin_cache()
        conn.close()

    entries = suggest_library_entries(samples, min_count=args.min_count)
    payload_out = {
        "_comment": (
            "Кандидаты в us_engine_map.json из vPIC (реальные VIN). Добавлять под ревью: "
            "hp = медиана наблюдений, cc номинальный (кратно 100), samples = сколько VIN подтвердило."
        ),
        "engines": entries,
    }
    text = json.dumps(payload_out, ensure_ascii=False, indent=2)
    print(text, flush=True)
    if args.json_out:
        out_path = Path(args.json_out)
        if not out_path.is_absolute():
            out_path = (Path.cwd() / out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"written {out_path}", flush=True)

    print(f"done scanned={scanned} vin_hits={vin_hits} entries={len(entries)}", flush=True)
    if uncovered:
        top = sorted(uncovered.items(), key=lambda kv: -kv[1])[:15]
        print("uncovered (нет VIN-данных — править библиотеку вручную):", flush=True)
        for name, n in top:
            print(f"  {n:4d}  {name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
