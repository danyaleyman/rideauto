"""Опциональный справочник OEM-диапазонов hp (JSON по env HP_ENGINE_OEM_HINTS_JSON).

Правило может задаваться:
  - needle — подстрока в нормализованном тексте типа топлива/движка;
  - needle_motor_norm — точное совпадение normalize_key_part(motor code);
  - needle_vin_prefix — vin_prefix строки каталога начинается с префикса (регистр верхний).
При нескольких band на одну строку достаточно одного попадания hp в диапазон.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, List, Optional

_RULES_CACHE: Optional[List[dict[str, Any]]] = None
_HINTS_MTIME: Optional[float] = None


def _load_rules(force: bool = False) -> List[dict[str, Any]]:
    global _RULES_CACHE, _HINTS_MTIME
    path = (os.environ.get("HP_ENGINE_OEM_HINTS_JSON") or "").strip()
    if not path:
        _RULES_CACHE = []
        return []
    fp = Path(path)
    if not fp.is_file():
        _RULES_CACHE = []
        return []
    try:
        mtime = fp.stat().st_mtime
    except OSError:
        _RULES_CACHE = []
        return []
    if not force and _RULES_CACHE is not None and _HINTS_MTIME == mtime:
        return _RULES_CACHE
    raw = fp.read_text(encoding="utf-8")
    blob = json.loads(raw)
    rules = blob.get("rules") if isinstance(blob, dict) else blob
    _RULES_CACHE = [x for x in rules if isinstance(x, dict)] if isinstance(rules, list) else []
    _HINTS_MTIME = mtime
    return _RULES_CACHE


def _norm_eng(s: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", s.lower())


def motor_code_oob_note_extended(
    engine_type_hint: Any,
    displacement_cc: Any,
    power_hp: int,
    *,
    motor_code_norm: str = "",
    vin_prefix: str = "",
) -> Optional[str]:
    """
    None — подсказок нет / ни одно правило по полям не сработало.
    \"\" — hp в допустимом диапазоне по сработавшему правилу.
    строка — вне допуска.
    """
    rules = _load_rules()
    if not rules:
        return None

    needle_space = _norm_eng(str(engine_type_hint or "").lower())
    mc = str(motor_code_norm or "").strip().lower()
    vp = str(vin_prefix or "").strip().upper()

    cc: Optional[int] = None
    if displacement_cc is not None:
        try:
            cci = int(displacement_cc)
            if cci > 0:
                cc = cci
        except (TypeError, ValueError):
            cc = None

    applicable_hp_rules: List[tuple[int, int]] = []

    for r in rules:
        matched = False
        needle = str(r.get("needle") or "").strip().lower()
        nmotor = str(r.get("needle_motor_norm") or "").strip().lower()
        nv = str(r.get("needle_vin_prefix") or "").strip().upper()

        if nmotor:
            matched = nmotor != "" and mc != "" and mc == nmotor
        elif nv:
            matched = nv != "" and vp != "" and vp.startswith(nv)
        elif needle:
            matched = needle in needle_space

        if not matched:
            continue

        if cc is None:
            continue
        cmin_raw, cmax_raw = r.get("cc_min"), r.get("cc_max")
        if cmin_raw is None or cmax_raw is None:
            continue
        try:
            ci, ca = int(cmin_raw), int(cmax_raw)
            if ci > ca:
                ci, ca = ca, ci
        except (TypeError, ValueError):
            continue
        if cc < ci or cc > ca:
            continue
        hmn, hmx = r.get("hp_min"), r.get("hp_max")
        if hmn is None or hmx is None:
            continue
        try:
            hmin, hmax = int(hmn), int(hmx)
            if hmin > hmax:
                hmin, hmax = hmax, hmin
        except (TypeError, ValueError):
            continue
        applicable_hp_rules.append((hmin, hmax))

    if not applicable_hp_rules:
        return None

    if any(lo <= power_hp <= hi for lo, hi in applicable_hp_rules):
        return ""
    return "oem_hints_range_mismatch"


def motor_code_oob_note(engine_type_hint: Any, displacement_cc: Any, power_hp: int) -> Optional[str]:
    """Совместимость: только engine_type строка без отдельного motor/VIN столбца."""
    return motor_code_oob_note_extended(
        engine_type_hint,
        displacement_cc,
        power_hp,
        motor_code_norm="",
        vin_prefix="",
    )
