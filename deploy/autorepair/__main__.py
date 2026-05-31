"""RideAuto autorepair — автономная диагностика и самовосстановление.

  python -m deploy.autorepair probe      # один снимок JSON
  python -m deploy.autorepair run-once   # один цикл probe→fix→verify
  python -m deploy.autorepair daemon     # фоновый цикл (systemd)

Перед продом: WRA_AUTOREPAIR_ENABLED=1 WRA_AUTOREPAIR_DRY_RUN=0
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import AutorepairConfig
from .engine import daemon_loop, run_cycle
from .probes import run_all_probes
from .state import AutorepairState


def cmd_probe(_: argparse.Namespace) -> int:
    cfg = AutorepairConfig.from_env()
    probes = run_all_probes(cfg)
    out = {cid: {"ok": pr.ok, "detail": pr.detail, "meta": pr.meta} for cid, pr in probes.items()}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(p["ok"] for p in out.values()) else 1


def cmd_run_once(_: argparse.Namespace) -> int:
    cfg = AutorepairConfig.from_env()
    state = AutorepairState.load(cfg.state_path)
    report = run_cycle(cfg, state)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("all_ok") or report.get("recovered") else 1


def cmd_daemon(_: argparse.Namespace) -> int:
    cfg = AutorepairConfig.from_env()
    if not cfg.enabled:
        print("WRA_AUTOREPAIR_ENABLED=0 — set to 1 for daemon", file=sys.stderr)
        return 2
    daemon_loop(cfg)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RideAuto autorepair agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="run all probes once").set_defaults(func=cmd_probe)
    sub.add_parser("run-once", help="one repair cycle").set_defaults(func=cmd_run_once)
    sub.add_parser("daemon", help="continuous loop").set_defaults(func=cmd_daemon)
    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
