"""Тесты планирования remediation (без shell)."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from deploy.autorepair.config import AutorepairConfig
from deploy.autorepair.probes import ProbeResult
from deploy.autorepair.remediate import plan_remediation


def test_plan_meili_sync_on_stale() -> None:
    cfg = AutorepairConfig.from_env()
    probes = {
        "postgres": ProbeResult("postgres", True),
        "api": ProbeResult("api", False, "stale", {"meili_stale": True}),
    }
    plan = plan_remediation(probes, cfg)
    assert plan is not None
    assert plan.action_key == "meili_sync"


def test_plan_restart_postgres() -> None:
    cfg = AutorepairConfig.from_env()
    probes = {"postgres": ProbeResult("postgres", False, "down")}
    plan = plan_remediation(probes, cfg)
    assert plan is not None
    assert plan.action_key == "restart:postgres"


def test_plan_none_when_healthy() -> None:
    cfg = AutorepairConfig.from_env()
    probes = {"api": ProbeResult("api", True)}
    assert plan_remediation(probes, cfg) is None
