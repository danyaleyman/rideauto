"""Безопасные действия починки (restart, meili sync, migrate)."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Optional

from .chain import component_by_id, find_root_cause
from .config import AutorepairConfig
from .probes import ProbeResult, run_all_probes
from .state import AutorepairState


@dataclass(frozen=True)
class RemediationPlan:
    action_key: str
    description: str
    component_id: str


def _run_shell(cfg: AutorepairConfig, shell: str, timeout: int = 600) -> tuple[int, str]:
    try:
        p = subprocess.run(
            shell,
            cwd=str(cfg.project_root),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out[-2000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except OSError as exc:
        return 127, str(exc)


def plan_remediation(
    probes: dict[str, ProbeResult],
    cfg: AutorepairConfig,
) -> Optional[RemediationPlan]:
    failed = {cid for cid, pr in probes.items() if not pr.ok}
    if not failed:
        return None

    chain = find_root_cause(failed)
    if not chain:
        return None

    target = chain[0]
    pr = probes.get(target)
    meta = (pr.meta if pr else {}) or {}

    if target == "meilisearch" or meta.get("meili_stale"):
        if cfg.allow_meili_sync:
            return RemediationPlan(
                "meili_sync",
                "Sync Meilisearch index from PostgreSQL",
                "meilisearch",
            )

    comp = component_by_id(target)
    if comp and comp.compose_service and cfg.allow_restart:
        return RemediationPlan(
            f"restart:{comp.compose_service}",
            f"docker compose restart {comp.compose_service}",
            target,
        )

    if target == "api" and cfg.allow_restart:
        return RemediationPlan("restart:api", "restart api", "api")

    return None


def execute_plan(
    plan: RemediationPlan,
    cfg: AutorepairConfig,
    state: AutorepairState,
) -> tuple[bool, str]:
    if not state.can_run_action(plan.action_key, cfg.cooldown_sec, cfg.max_actions_per_hour):
        return False, f"cooldown active for {plan.action_key}"

    if cfg.dry_run:
        state.log_event(cfg.log_path, {"event": "dry_run", "plan": plan.description})
        return True, f"[dry-run] would: {plan.description}"

    if plan.action_key == "meili_sync":
        code, out = _run_shell(
            cfg,
            "docker compose exec -T api python /app/infrastructure/meilisearch/sync_meilisearch.py "
            '--pg-dsn "$WRA_PG_DSN" --meili-url "$WRA_MEILISEARCH_URL" --meili-key "$WRA_MEILISEARCH_KEY"',
            timeout=7200,
        )
    elif plan.action_key.startswith("restart:"):
        svc = plan.action_key.split(":", 1)[1]
        code, out = _run_shell(cfg, f"docker compose restart {svc}", timeout=300)
        if code == 0:
            time.sleep(5)
            _run_shell(cfg, f"docker compose up -d {svc}", timeout=120)
    elif plan.action_key == "migrate_apply" and cfg.allow_migrate:
        code, out = _run_shell(
            cfg,
            "docker compose exec -T api python /app/infrastructure/postgresql/migrate.py apply",
            timeout=600,
        )
    else:
        return False, f"unknown action {plan.action_key}"

    state.record_action(plan.action_key)
    state.log_event(
        cfg.log_path,
        {
            "event": "remediation",
            "action": plan.action_key,
            "component": plan.component_id,
            "exit_code": code,
            "output_tail": out[-500:],
        },
    )
    return code == 0, out[-500:] if code != 0 else "ok"


def verify_recovery(cfg: AutorepairConfig, wait_sec: int = 15) -> bool:
    time.sleep(wait_sec)
    probes = run_all_probes(cfg)
    return all(pr.ok for pr in probes.values())
