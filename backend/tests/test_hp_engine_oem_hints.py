import json
from pathlib import Path

import pytest

import hp_engine_oem_hints as m


def test_oem_hints_in_band_suppress(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hints = tmp_path / "oem.json"
    hints.write_text(
        json.dumps(
            {
                "rules": [
                    {"needle": "g4na", "cc_min": 1990, "cc_max": 2010, "hp_min": 150, "hp_max": 160},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HP_ENGINE_OEM_HINTS_JSON", str(hints))
    m._RULES_CACHE = None
    m._HINTS_MTIME = None  # noqa: SLF001
    assert m.motor_code_oob_note(" gasoline G4NA korea", 1998, 155) == ""


def test_oem_hints_needle_motor_norm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hints = tmp_path / "oem_motor.json"
    hints.write_text(
        json.dumps(
            {
                "rules": [
                    {"needle_motor_norm": "g4na", "cc_min": 1990, "cc_max": 2010, "hp_min": 150, "hp_max": 160},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HP_ENGINE_OEM_HINTS_JSON", str(hints))
    m._RULES_CACHE = None
    m._HINTS_MTIME = None  # noqa: SLF001
    assert (
        m.motor_code_oob_note_extended("unrelated gasoline", 1998, 155, motor_code_norm="g4na", vin_prefix="")
        == ""
    )
    assert (
        m.motor_code_oob_note_extended("unrelated gasoline", 1998, 155, motor_code_norm="wrong", vin_prefix="")
        is None
    )


def test_oem_hints_needle_vin_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hints = tmp_path / "oem_vin.json"
    hints.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "needle_vin_prefix": "KMH",
                        "cc_min": 1590,
                        "cc_max": 1610,
                        "hp_min": 140,
                        "hp_max": 155,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HP_ENGINE_OEM_HINTS_JSON", str(hints))
    m._RULES_CACHE = None
    m._HINTS_MTIME = None  # noqa: SLF001
    assert (
        m.motor_code_oob_note_extended("gasoline", 1600, 148, motor_code_norm="", vin_prefix="KMHWXXXXXXXX")
        == ""
    )
    assert (
        m.motor_code_oob_note_extended(
            "gasoline", 1600, 500, motor_code_norm="", vin_prefix="KMHWXXXXXXXX"
        )
        == "oem_hints_range_mismatch"
    )


def test_oem_hints_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hints = tmp_path / "oem2.json"
    hints.write_text(
        json.dumps(
            {
                "rules": [
                    {"needle": "g4na", "cc_min": 1990, "cc_max": 2010, "hp_min": 150, "hp_max": 160},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HP_ENGINE_OEM_HINTS_JSON", str(hints))
    m._RULES_CACHE = None
    m._HINTS_MTIME = None  # noqa: SLF001
    assert m.motor_code_oob_note("G4NA", 1998, 500) == "oem_hints_range_mismatch"
