"""Цикл: probe → diagnose → remediate → verify."""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

from .config import AutorepairConfig
from .probes import run_all_probes
from .remediate import execute_plan, plan_remediation, verify_recovery
from .state import AutorepairState


def _notify_webhook(cfg: AutorepairConfig, text: str) -> None:
    if not cfg.webhook_url:
        return
    try:
        body = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            cfg.webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def run_cycle(cfg: AutorepairConfig, state: AutorepairState) -> dict[str, Any]:
    probes = run_all_probes(cfg)
    failed = {cid: {"ok": pr.ok, "detail": pr.detail} for cid, pr in probes.items()}
    all_ok = all(pr.ok for pr in probes.values())

    report: dict[str, Any] = {
        "ts": time.time(),
        "all_ok": all_ok,
        "probes": failed,
        "dry_run": cfg.dry_run,
    }

    if all_ok:
        state.consecutive_failures = 0
        state.last_ok_at = time.time()
        state.save(cfg.state_path)
        return report

    state.consecutive_failures += 1
    state.last_incident_at = time.time()
    plan = plan_remediation(probes, cfg)
    report["plan"] = plan.description if plan else None

    if plan and cfg.enabled:
        ok, msg = execute_plan(plan, cfg, state)
        report["remediation"] = {"ok": ok, "message": msg}
        if ok and not cfg.dry_run:
            recovered = verify_recovery(cfg)
            report["recovered"] = recovered
            if recovered:
                state.consecutive_failures = 0
    elif not cfg.enabled:
        report["remediation"] = {"ok": False, "message": "WRA_AUTOREPAIR_ENABLED=0"}

    if state.consecutive_failures >= cfg.escalate_after_failures:
        text = (
            f"RideAuto autorepair: {state.consecutive_failures} failed cycles. "
            f"Last plan: {report.get('plan')}. Probes: {failed}"
        )
        _notify_webhook(cfg, text)
        report["escalated"] = True

    state.save(cfg.state_path)
    state.log_event(cfg.log_path, report)
    return report


def daemon_loop(cfg: AutorepairConfig) -> None:
    state = AutorepairState.load(cfg.state_path)
    state.log_event(cfg.log_path, {"event": "daemon_start", "interval": cfg.interval_sec})
    while True:
        try:
            report = run_cycle(cfg, state)
            if not report.get("all_ok"):
                print(
                    f"[autorepair] incident plan={report.get('plan')} "
                    f"recovered={report.get('recovered')}",
                    flush=True,
                )
        except Exception as exc:
            state.log_event(cfg.log_path, {"event": "cycle_error", "error": str(exc)[:300]})
            print(f"[autorepair] cycle error: {exc}", flush=True)
        time.sleep(cfg.interval_sec)
