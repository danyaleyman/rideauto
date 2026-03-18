# -*- coding: utf-8 -*-
"""
Мощность (л.с.) из локальной базы power_lookup.json (марка/модель/год/объём).
Используется при экспорте для подстановки мощности, если в парсере не найдена.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "frontend" / "data"
POWER_LOOKUP_PATH = DATA_DIR / "power_lookup.json"


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip()).lower()


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


def _load_power_lookup() -> List[Dict[str, Any]]:
    if not POWER_LOOKUP_PATH.exists():
        return []
    try:
        with open(POWER_LOOKUP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


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


def get_power_for_car(car_data: Dict[str, Any]) -> Optional[int]:
    """
    Получить мощность (л.с.) для авто: уже есть в данных или из power_lookup.json.
    """
    if not isinstance(car_data, dict):
        return None
    if car_data.get("power") and str(car_data.get("power", "")).strip():
        try:
            return int(re.sub(r"\D", "", str(car_data["power"])))
        except ValueError:
            pass
    return get_power_from_lookup(car_data)
