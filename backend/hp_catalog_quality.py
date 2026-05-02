"""Дополнительные эвристики качества строк hp_catalog (без официальных справочников)."""
from __future__ import annotations

import math
import os
from typing import Any, Optional


def _float_env(key: str, default: float) -> float:
    raw = str(os.environ.get(key) or "").strip()
    if not raw:
        return default
    try:
        v = float(raw)
        return v if math.isfinite(v) else default
    except ValueError:
        return default


def secondary_review_hint_with_env(
    *,
    displacement_cc: Any,
    power_hp: int,
    engine_type: str,
) -> Optional[str]:
    """
    Пороги через env для снижения ложных срабатываний на редких моторах:
      HP_REVIEW_HIGH_HP_RATIO_LOW / HP_REVIEW_HIGH_HP_RATIO_HIGH — л.с. на литр верхней «серыой»
      HP_REVIEW_LARGE_DISP_CC_MIN — порог литража для «низкой удельной»
      HP_REVIEW_LARGE_DISP_HP_RATIO_MAX — макс hp/л для «тяжёлого блока»
    """
    et = str(engine_type or "")
    et_l = et.lower()
    if any(x in et for x in ("전기",)):
        et_l = f"{et_l} ev"
    if "electric" in et_l or "ev " in et_l or et_l.strip() in ("ev",):
        return None

    cc: Optional[int] = None
    if displacement_cc is not None:
        try:
            cc_i = int(displacement_cc)
            if cc_i > 0:
                cc = cc_i
        except (TypeError, ValueError):
            cc = None
    cc_min_gray = _float_env("HP_REVIEW_MIN_CC_GRAY_HEURISTIC", 1600)

    if cc is None or cc < cc_min_gray:
        return None

    liters = cc / 1000.0
    ratio = power_hp / liters if liters > 1e-6 else 999.0

    hi_lo = _float_env("HP_REVIEW_HIGH_HP_RATIO_LOW", 215.0)
    hi_hi = _float_env("HP_REVIEW_HIGH_HP_RATIO_HIGH", 270.0)
    ld_cc = _float_env("HP_REVIEW_LARGE_DISP_CC_MIN", 3000.0)
    ld_max_ratio = _float_env("HP_REVIEW_LARGE_DISP_HP_RATIO_MAX", 85.0)

    if cc >= cc_min_gray and hi_lo <= ratio <= hi_hi:
        return "high_hp_per_liter_gray_zone"
    if cc >= ld_cc and ratio <= ld_max_ratio:
        return "large_displacement_low_hp_gray_zone"

    return None


def secondary_review_hint(
    *,
    displacement_cc: Any,
    power_hp: int,
    engine_type: str,
) -> Optional[str]:
    """Стабильный API; см. переменные окружения в secondary_review_hint_with_env."""
    return secondary_review_hint_with_env(
        displacement_cc=displacement_cc,
        power_hp=power_hp,
        engine_type=str(engine_type or ""),
    )
