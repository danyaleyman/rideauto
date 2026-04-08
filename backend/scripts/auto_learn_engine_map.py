#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автообучение engine_map.json по выгрузке машин.

Тянет данные сам (Postgres / cars.json / chunks), не дублирует id.
Берёт только машины с реальной мощностью (не из engine_map), с кодом двигателя
motorType из инспекции Encar (extra.inspection.master.detail.motorType).

Запуск (из корня репозитория или откуда угодно):
  python backend/scripts/auto_learn_engine_map.py
  python backend/scripts/auto_learn_engine_map.py --dry-run
  AUTO_LEARN_ENGINE_MAP=1  — после postgres_catalog_sync

Зависимости: только stdlib + engine_hp_resolver (рядом в backend/).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple

# backend/ в PYTHONPATH
_BACKEND = Path(__file__).resolve().parent.parent
_REPO = _BACKEND.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from engine_hp_resolver import (  # noqa: E402
    _load_mark_ko_to_en,
    detect_turbo,
    extract_motor_code,
    _car_cc,
    _fuel_bucket,
)


def _norm_make_en(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _make_display_name(car_data: Dict[str, Any]) -> str:
    raw = (car_data.get("manufacturerName") or car_data.get("mark") or "").strip()
    if not raw:
        return "Unknown"
    m = _load_mark_ko_to_en().get(raw)
    if m:
        return str(m).strip()
    return raw


def _parse_hp_trusted(car_data: Dict[str, Any]) -> Optional[int]:
    """Мощность только если не наша оценка с engine_map (избегаем петли)."""
    if car_data.get("power_source") == "engine_map":
        return None
    if car_data.get("power_estimated") is True:
        return None
    p = car_data.get("power")
    if p is None or str(p).strip() == "":
        return None
    try:
        n = int(re.sub(r"\D", "", str(p)))
        if 20 <= n <= 2000:
            return n
    except ValueError:
        pass
    return None


def _iter_cars_from_json(path: Path) -> Generator[Dict[str, Any], None, None]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("result"), list):
        for c in data["result"]:
            if isinstance(c, dict) and isinstance(c.get("data"), dict):
                yield c["data"]
            elif isinstance(c, dict):
                yield c
    elif isinstance(data, list):
        for c in data:
            if isinstance(c, dict) and isinstance(c.get("data"), dict):
                yield c["data"]


def _iter_cars_from_chunks(chunks_dir: Path) -> Generator[Dict[str, Any], None, None]:
    for p in sorted(chunks_dir.glob("cars_*.json")):
        yield from _iter_cars_from_json(p)


def _iter_cars_from_postgres(dsn: str) -> Generator[Dict[str, Any], None, None]:
    import psycopg2

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM cars")
            for (row,) in cur.fetchall():
                if row is None:
                    continue
                if isinstance(row, dict):
                    car = row
                elif isinstance(row, (bytes, memoryview)):
                    try:
                        car = json.loads(bytes(row).decode("utf-8"))
                    except Exception:
                        continue
                else:
                    try:
                        car = json.loads(str(row))
                    except Exception:
                        continue
                if isinstance(car, dict) and isinstance(car.get("data"), dict):
                    yield car["data"]
                elif isinstance(car, dict):
                    yield car


def discover_car_stream(repo: Path) -> Tuple[str, Iterable[Dict[str, Any]]]:
    """Источник: DATABASE_URL → Postgres, иначе web/public/cars.json, иначе chunks."""
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if dsn:
        return ("postgresql://cars.data", _iter_cars_from_postgres(dsn))
    cars_json = repo / "web" / "public" / "cars.json"
    if cars_json.exists():
        return ("web/public/cars.json", _iter_cars_from_json(cars_json))
    chunks = repo / "web" / "public" / "data" / "chunks"
    if chunks.is_dir() and list(chunks.glob("cars_*.json")):
        return ("web/public/data/chunks/*.json", _iter_cars_from_chunks(chunks))
    raise FileNotFoundError(
        f"Нет данных: задайте DATABASE_URL или положите {cars_json} / chunks в web/public/data/chunks"
    )


def unique_by_car_id(stream: Iterable[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
    seen: set = set()
    for d in stream:
        cid = d.get("id") or d.get("inner_id")
        key = str(cid) if cid is not None else None
        if key:
            if key in seen:
                continue
            seen.add(key)
        yield d


GroupKey = Tuple[str, str, int, str, bool]  # make_en, motor, cc, fuel, turbo


def _group_key(car_data: Dict[str, Any]) -> Optional[GroupKey]:
    motor = extract_motor_code(car_data)
    if not motor or len(motor) < 3:
        return None
    cc = _car_cc(car_data)
    if cc is None:
        return None
    fuel = _fuel_bucket(car_data.get("engine_type")) or "gas"
    turbo = detect_turbo(car_data)
    mk = _norm_make_en(_make_display_name(car_data))
    if not mk:
        return None
    return (mk, motor.upper(), int(cc), str(fuel), bool(turbo))


def learn_groups(
    cars: Iterable[Dict[str, Any]],
    min_count: int,
    max_stdev: float,
) -> Dict[GroupKey, Dict[str, Any]]:
    """Группа → median hp, sample_count, cc range, example car for make label."""
    buckets: Dict[GroupKey, List[int]] = defaultdict(list)
    cc_ranges: Dict[GroupKey, List[int]] = defaultdict(list)
    example: Dict[GroupKey, Dict[str, Any]] = {}

    for d in cars:
        hp = _parse_hp_trusted(d)
        if hp is None:
            continue
        gk = _group_key(d)
        if gk is None:
            continue
        # Ошибочный fuel=electric при ICE (код мотора Mercedes и т.п.) — не учим
        if gk[3] == "electric" and "tesla" not in gk[0]:
            continue
        buckets[gk].append(hp)
        cc_ranges[gk].append(gk[2])
        if gk not in example:
            example[gk] = d

    out: Dict[GroupKey, Dict[str, Any]] = {}
    for gk, hps in buckets.items():
        if len(hps) < min_count:
            continue
        if len(hps) >= 2 and statistics.pstdev(hps) > max_stdev:
            continue
        median_hp = int(round(statistics.median(hps)))
        ccs = cc_ranges[gk]
        out[gk] = {
            "hp": median_hp,
            "sample_count": len(hps),
            "cc_min": min(ccs),
            "cc_max": max(ccs),
            "example": example[gk],
        }
    return out


def _learned_entry(gk: GroupKey, info: Dict[str, Any]) -> Dict[str, Any]:
    _, motor, _, fuel, turbo = gk
    car = info["example"]
    make_label = _make_display_name(car)
    return {
        "make": make_label,
        "make_ko": (car.get("manufacturerName") or car.get("mark") or "").strip() or None,
        "motor_codes": [motor],
        "cc_min": int(info["cc_min"]),
        "cc_max": int(info["cc_max"]),
        "turbo": turbo,
        "fuel": fuel,
        "hp": int(info["hp"]),
        "priority": min(12 + min(info["sample_count"], 15), 25),
        "source": "learned",
        "auto_learned": True,
        "sample_count": int(info["sample_count"]),
    }


def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def load_engine_map_file(path: Path) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    if not path.exists():
        return (
            "Каталог двигателей; ручные строки + auto_learned из скрипта auto_learn_engine_map.py",
            [],
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    comment = None
    if isinstance(data, dict):
        comment = data.get("_comment")
        engines = data.get("engines")
        if isinstance(engines, list):
            return (comment, [e for e in engines if isinstance(e, dict)])
        return (comment, [])
    if isinstance(data, list):
        return (None, [e for e in data if isinstance(e, dict)])
    return (None, [])


def _manual_key(e: Dict[str, Any]) -> Tuple[str, Tuple[str, ...], Optional[int], Optional[int], Optional[int]]:
    """Ключ для конфликта с learned (по motor_codes)."""
    make = _norm_make_en(str(e.get("make") or ""))
    codes = tuple(
        sorted(str(c).upper() for c in (e.get("motor_codes") or e.get("engine_codes") or []))
    )
    return (
        make,
        codes,
        e.get("cc_min"),
        e.get("cc_max"),
        e.get("cc"),
    )


def merge_learned(
    existing: List[Dict[str, Any]],
    learned: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Удаляем старые auto_learned, добавляем новые; не трогаем ручные; не дублируем motor вручную."""
    manual_motor_keys = set()
    for e in existing:
        if e.get("auto_learned"):
            continue
        codes = e.get("motor_codes") or e.get("engine_codes") or []
        if codes:
            manual_motor_keys.add(_manual_key(e))

    kept = [e for e in existing if not e.get("auto_learned")]
    for le in learned:
        mk = _manual_key(le)
        if mk in manual_motor_keys:
            continue
        kept.append(_strip_none(le))
    return kept


def main() -> int:
    parser = argparse.ArgumentParser(description="Обучение engine_map.json по выгрузке")
    parser.add_argument("--repo", type=Path, default=_REPO, help="Корень репозитория")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Путь к engine_map.json (по умолчанию data/engine_map.json)",
    )
    parser.add_argument("--min-count", type=int, default=3, help="Мин. машин в группе")
    parser.add_argument(
        "--max-stdev",
        type=float,
        default=28.0,
        help="Макс. разброс л.с. в группе (отсекаем неоднородные)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Только отчёт, без записи")
    args = parser.parse_args()

    repo = args.repo.resolve()
    out_path = args.output or (repo / "data" / "engine_map.json")

    try:
        source_label, stream = discover_car_stream(repo)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    cars = list(unique_by_car_id(stream))
    print(f"Источник: {source_label}, уникальных записей: {len(cars)}")

    groups = learn_groups(cars, args.min_count, args.max_stdev)
    learned_entries = [_learned_entry(gk, info) for gk, info in sorted(groups.items())]

    print(f"Новых learned-групп (motorType + cc + топливо + турбо): {len(learned_entries)}")
    for le in learned_entries[:15]:
        print(
            f"  {le['make']} motor={le['motor_codes'][0]} "
            f"{le['cc_min']}-{le['cc_max']}cc {le['fuel']} turbo={le['turbo']} -> {le['hp']} hp (n={le['sample_count']})"
        )
    if len(learned_entries) > 15:
        print(f"  ... и ещё {len(learned_entries) - 15}")

    if args.dry_run:
        print("Dry-run: файл не записан.")
        return 0

    comment, engines = load_engine_map_file(out_path)
    merged = merge_learned(engines, learned_entries)
    payload: Dict[str, Any] = {"engines": merged}
    if comment:
        payload["_comment"] = comment

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Записано: {out_path} (всего записей: {len(merged)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
