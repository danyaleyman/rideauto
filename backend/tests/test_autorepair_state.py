"""Тесты cooldown и persistence autorepair state."""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AR_DIR = _REPO_ROOT / "deploy" / "autorepair"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _AR_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


state_mod = _load("rideauto_autorepair_state", "state.py")


def test_cooldown_blocks_repeat(tmp_path: Path) -> None:
    s = state_mod.AutorepairState()
    assert s.can_run_action("restart:api", cooldown_sec=60, max_per_hour=10)
    s.record_action("restart:api")
    assert not s.can_run_action("restart:api", cooldown_sec=60, max_per_hour=10)


def test_save_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    s = state_mod.AutorepairState(consecutive_failures=3)
    s.record_action("meili_sync")
    s.save(p)
    loaded = state_mod.AutorepairState.load(p)
    assert loaded.consecutive_failures == 3
    assert "meili_sync" in loaded.last_actions


def test_max_actions_per_hour(tmp_path: Path) -> None:
    s = state_mod.AutorepairState()
    now = time.time()
    s.actions_this_hour = [now - 10] * 5
    assert not s.can_run_action("x", cooldown_sec=0, max_per_hour=5)
