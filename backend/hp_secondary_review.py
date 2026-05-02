"""Объединяет OEM-подсказки (motor / VIN / engine string) и эвристику л.с./литр для review_flag."""
from __future__ import annotations

import os
from typing import Any, Optional

from hp_catalog_quality import secondary_review_hint_with_env
from hp_engine_oem_hints import motor_code_oob_note_extended


def combined_review_note(
    *,
    displacement_cc: Any,
    power_hp: int,
    engine_type: str,
    motor_code_norm: str = "",
    vin_prefix: str = "",
) -> Optional[tuple[bool, str]]:
    oem = motor_code_oob_note_extended(
        engine_type,
        displacement_cc,
        power_hp,
        motor_code_norm=motor_code_norm,
        vin_prefix=vin_prefix,
    )
    if oem == "":
        return (False, "")
    if isinstance(oem, str) and oem:
        return True, oem

    if str(os.environ.get("HP_REVIEW_RATIO_HEURISTIC", "") or "").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return None

    ratio = secondary_review_hint_with_env(
        displacement_cc=displacement_cc,
        power_hp=power_hp,
        engine_type=str(engine_type or ""),
    )
    return (True, ratio) if ratio else None


def finalize_review_fields(
    *,
    displacement_cc: Any,
    power_hp: int,
    engine_type: str,
    motor_code_norm: str = "",
    vin_prefix: str = "",
) -> tuple[int, str]:
    combo = combined_review_note(
        displacement_cc=displacement_cc,
        power_hp=power_hp,
        engine_type=str(engine_type or ""),
        motor_code_norm=str(motor_code_norm or ""),
        vin_prefix=str(vin_prefix or ""),
    )
    if combo is None:
        return 0, ""
    flagged, txt = combo
    if flagged:
        return 1, (txt or "")[:200]
    return 0, ""
