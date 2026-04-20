# -*- coding: utf-8 -*-
"""
Мощность (л.с.): 1) уже в данных авто, 2) data/hp_catalog.db, 3) engine_map.json,
4) ручной список power_lookup.json.

Если запись не найдена в hp_catalog.db, добавляем pending-строку для фонового LLM-fill.
"""
from __future__ import annotations

import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POWER_LOOKUP_PATH = DATA_DIR / "power_lookup.json"
HP_CATALOG_DB_PATH = DATA_DIR / "hp_catalog.db"
_NON_WORD_RE = re.compile(r"[^0-9a-zA-Z가-힣]+")


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip()).lower()


def _norm_key(s: Any) -> str:
    return _NON_WORD_RE.sub("", _norm(s))


def _norm_disp(disp: Any) -> str:
    if disp is None or disp == "":
        return ""
    try:
        n = int(re.sub(r"\D", "", str(disp)))
        if 500 <= n <= 8000:
            return str(n)
    except ValueError:
        pass
    return ""


def _norm_ym(value: Any) -> str:
    if value is None:
        return ""
    digits = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if len(digits) >= 6:
        return digits[:6]
    if len(digits) == 4:
        return f"{digits}01"
    return ""


def _year_to_ym_candidates(value: str) -> List[str]:
    if not value:
        return []
    if len(value) == 4:
        return [f"{value}{m:02d}" for m in range(1, 13)]
    if len(value) == 6:
        return [value]
    return []


def _version_candidates(car_data: Dict[str, Any]) -> List[str]:
    vals: List[str] = []
    for key in ("gradeName", "generation", "configuration", "trim_name", "version"):
        v = _norm_key(car_data.get(key))
        if v and v not in vals:
            vals.append(v)
    return vals


def _load_power_lookup() -> List[Dict[str, Any]]:
    if not POWER_LOOKUP_PATH.exists():
        return []
    try:
        with open(POWER_LOOKUP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


@lru_cache(maxsize=1)
def _load_hp_catalog_index() -> Dict[str, int]:
    """in-memory индексы hp_catalog для быстрого поиска."""
    out: Dict[str, int] = {}
    if not HP_CATALOG_DB_PATH.is_file():
        return out
    try:
        conn = sqlite3.connect(str(HP_CATALOG_DB_PATH))
        try:
            rows = conn.execute(
                """
                SELECT
                    norm_manufacturer, norm_model, norm_version, norm_engine_type,
                    displacement_cc, year_month, power_hp
                FROM hp_catalog
                WHERE power_hp IS NOT NULL AND power_hp > 0
                """
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return out
    for nm, nmd, nv, net, dcc, ym, hp in rows:
        try:
            hpv = int(hp)
        except (TypeError, ValueError):
            continue
        if not (20 <= hpv <= 2500):
            continue
        keys = _hp_catalog_keys(
            nm=str(nm or ""),
            nmd=str(nmd or ""),
            nv=str(nv or ""),
            net=str(net or ""),
            dcc=str(int(dcc)) if dcc not in (None, "") else "",
            ym=str(ym or ""),
        )
        for k in keys:
            out.setdefault(k, hpv)
    return out


def _hp_catalog_keys(*, nm: str, nmd: str, nv: str, net: str, dcc: str, ym: str) -> Tuple[str, ...]:
    """Ключи приоритета: от точного к мягкому."""
    # keep versioned first, then no-version variants
    return (
        f"{nm}|{nmd}|{nv}|{net}|{dcc}|{ym}",
        f"{nm}|{nmd}|{nv}|{net}|{dcc}|",
        f"{nm}|{nmd}||{net}|{dcc}|{ym}",
        f"{nm}|{nmd}||{net}|{dcc}|",
        f"{nm}|{nmd}|||{dcc}|{ym}",
        f"{nm}|{nmd}|||{dcc}|",
    )


def _hp_catalog_lookup(car_data: Dict[str, Any]) -> Optional[int]:
    idx = _load_hp_catalog_index()
    if not idx:
        return None
    nm = _norm_key(car_data.get("mark") or car_data.get("manufacturer") or car_data.get("manufacturerName"))
    nmd = _norm_key(car_data.get("model") or car_data.get("modelName"))
    if not nm or not nmd:
        return None
    net = _norm_key(car_data.get("engine_type") or car_data.get("fuel") or car_data.get("engineType"))
    dcc = _norm_disp(car_data.get("displacement") or car_data.get("displacement_cc") or car_data.get("engine_volume"))
    ym = _norm_ym(car_data.get("yearMonth") or car_data.get("year_month") or car_data.get("year"))
    yms = _year_to_ym_candidates(ym) if ym else [""]
    versions = _version_candidates(car_data) or [""]
    for v in versions:
        for ymv in yms:
            for key in _hp_catalog_keys(nm=nm, nmd=nmd, nv=v, net=net, dcc=dcc, ym=ymv):
                hp = idx.get(key)
                if hp is not None:
                    return hp
    return None


def _enqueue_hp_catalog_pending(car_data: Dict[str, Any]) -> None:
    """Регистрирует пропуск в hp_catalog для фонового LLM-филла."""
    if not HP_CATALOG_DB_PATH.parent.exists():
        return
    manufacturer = str(car_data.get("mark") or car_data.get("manufacturer") or car_data.get("manufacturerName") or "").strip()
    model = str(car_data.get("model") or car_data.get("modelName") or "").strip()
    if not manufacturer or not model:
        return
    version = str(
        car_data.get("gradeName")
        or car_data.get("generation")
        or car_data.get("configuration")
        or car_data.get("trim_name")
        or ""
    ).strip()
    engine_type = str(car_data.get("engine_type") or car_data.get("fuel") or car_data.get("engineType") or "").strip()
    displacement_cc = _norm_disp(car_data.get("displacement") or car_data.get("displacement_cc") or car_data.get("engine_volume"))
    year_month = _norm_ym(car_data.get("yearMonth") or car_data.get("year_month") or car_data.get("year"))
    try:
        conn = sqlite3.connect(str(HP_CATALOG_DB_PATH))
        try:
            conn.execute(
                """
                INSERT INTO hp_catalog (
                    manufacturer, model, version, engine_type, displacement_cc, drive, year_month,
                    norm_manufacturer, norm_model, norm_version, norm_engine_type,
                    llm_status, source
                ) VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, 'pending', 'catalog')
                ON CONFLICT(norm_manufacturer, norm_model, norm_version, norm_engine_type, COALESCE(displacement_cc, -1), year_month)
                DO UPDATE SET updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                """,
                (
                    manufacturer,
                    model,
                    version,
                    engine_type,
                    int(displacement_cc) if displacement_cc else None,
                    year_month,
                    _norm_key(manufacturer),
                    _norm_key(model),
                    _norm_key(version),
                    _norm_key(engine_type),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Не роняем основной sync из-за вспомогательной очереди.
        return


def get_power_from_lookup(car_data: Dict[str, Any]) -> Optional[int]:
    """
    Мощность из локальной базы data/power_lookup.json.
    Формат: список объектов с полями make, model, year, displacement (опционально), power.
    """
    entries = _load_power_lookup()
    if not entries:
        return None
    make = _norm(car_data.get("mark") or car_data.get("manufacturer") or car_data.get("manufacturerName") or "")
    model = _norm(car_data.get("model") or car_data.get("modelName") or "")
    year = (car_data.get("year") or car_data.get("yearMonth") or "")
    if year:
        year = str(year).strip()[:4]
    disp = _norm_disp(car_data.get("displacement"))
    if not make and not model:
        return None
    for e in entries:
        e_make = _norm(e.get("make") or e.get("brand") or "")
        e_model = _norm(e.get("model") or "")
        e_year = str(e.get("year") or "").strip()[:4]
        e_disp = _norm_disp(e.get("displacement"))
        e_power = e.get("power") or e.get("horsepower") or e.get("hp")
        if e_power is None:
            continue
        try:
            hp = int(e_power)
        except (TypeError, ValueError):
            continue
        if not (20 <= hp <= 2000):
            continue
        if e_make and make and e_make not in make and make not in e_make:
            continue
        if e_model and model and e_model not in model and model not in e_model:
            continue
        if e_year and year and e_year != year:
            continue
        if e_disp and disp and e_disp != disp:
            continue
        return hp
    return None


def get_power_for_car(
    car_data: Dict[str, Any],
    *,
    record_source: bool = False,
) -> Optional[int]:
    """
    Получить мощность (л.с.): из данных, hp_catalog.db, engine_map.json, power_lookup.json.
    record_source=True — записать power_source / power_estimated при обогащении.
    """
    if not isinstance(car_data, dict):
        return None
    if car_data.get("power") and str(car_data.get("power", "")).strip():
        try:
            return int(re.sub(r"\D", "", str(car_data["power"])))
        except ValueError:
            pass

    hp_catalog = _hp_catalog_lookup(car_data)
    if hp_catalog is not None:
        if record_source:
            car_data.setdefault("power_source", "hp_catalog")
        return hp_catalog

    try:
        from engine_hp_resolver import resolve_engine_hp

        hp_map = resolve_engine_hp(car_data, record_source=record_source)
        if hp_map is not None:
            return hp_map
    except ImportError:
        pass

    hp_lookup = get_power_from_lookup(car_data)
    if hp_lookup is not None:
        if record_source:
            car_data.setdefault("power_source", "power_lookup")
        return hp_lookup

    _enqueue_hp_catalog_pending(car_data)
    return None
