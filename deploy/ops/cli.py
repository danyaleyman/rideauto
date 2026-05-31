"""CLI параметризованных удалённых операций RideAuto.

Запуск:  python -m deploy.ops <command> [...]
Конфиг:  env-переменные RIDEAUTO_DEPLOY_* или deploy/.env.deploy (см. README.md).

Заменяет десятки одноразовых deploy/scripts/_remote_*.py: хост/логин/секреты больше
не хранятся в исходниках.
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from . import commands as cmd
from .config import RemoteConfig
from .ssh import RemoteSession


def _session(args: argparse.Namespace) -> RemoteSession:
    config = RemoteConfig.from_env()
    if args.verbose:
        print(f"[ops] connecting {config.redacted()}", file=sys.stderr)
    return RemoteSession(config)


def cmd_status(args: argparse.Namespace) -> int:
    with _session(args) as s:
        s.run_in_root(cmd.compose(["ps"]))
        s.run("curl -fsS http://127.0.0.1:8080/api/health || echo 'health: FAIL'")
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    with _session(args) as s:
        r = s.run("curl -fsS http://127.0.0.1:8080/api/health?deep=1")
    return 0 if r.exit_code == 0 else 1


def cmd_run(args: argparse.Namespace) -> int:
    remote_cmd = " ".join(args.cmd)
    if not remote_cmd.strip():
        print("usage: run -- <command>", file=sys.stderr)
        return 2
    with _session(args) as s:
        r = s.run_in_root(remote_cmd, timeout=args.timeout)
    return r.exit_code


def cmd_compose(args: argparse.Namespace) -> int:
    with _session(args) as s:
        r = s.run_in_root(cmd.compose(args.args), timeout=args.timeout)
    return r.exit_code


def cmd_api_exec(args: argparse.Namespace) -> int:
    inner = " ".join(args.cmd)
    with _session(args) as s:
        r = s.run_in_root(cmd.api_exec(inner), timeout=args.timeout)
    return r.exit_code


def cmd_psql(args: argparse.Namespace) -> int:
    sql = " ".join(args.sql)
    with _session(args) as s:
        r = s.run_in_root(cmd.postgres_exec(sql), timeout=args.timeout)
    return r.exit_code


def cmd_migrate(args: argparse.Namespace) -> int:
    with _session(args) as s:
        r = s.run_in_root(cmd.migrate(args.action), timeout=args.timeout)
    return r.exit_code


def cmd_meili_sync(args: argparse.Namespace) -> int:
    with _session(args) as s:
        r = s.run_in_root(
            cmd.meili_sync(preflight_gate=args.preflight_gate),
            timeout=args.timeout,
        )
    return r.exit_code


def cmd_rebuild_web(args: argparse.Namespace) -> int:
    with _session(args) as s:
        r = s.run_in_root(cmd.rebuild_web(), timeout=args.timeout)
    return r.exit_code


def cmd_deploy(args: argparse.Namespace) -> int:
    with _session(args) as s:
        s.run_in_root(cmd.git_pull(), timeout=args.timeout)
        r = s.run_in_root(cmd.rebuild_web(), timeout=args.timeout)
        if not args.skip_migrate:
            s.run_in_root(cmd.migrate("apply"), timeout=args.timeout)
            s.run_in_root(cmd.migrate("check"), timeout=args.timeout)
    return r.exit_code


def cmd_tail(args: argparse.Namespace) -> int:
    with _session(args) as s:
        r = s.run_in_root(cmd.tail_file(args.path, args.lines), timeout=args.timeout)
    return r.exit_code


def cmd_upload(args: argparse.Namespace) -> int:
    with _session(args) as s:
        s.put(args.local, args.remote)
        print(f"uploaded {args.local} -> {args.remote}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deploy.ops",
        description="RideAuto parameterized remote operations (no secrets in source)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--timeout", type=int, default=900, help="remote command timeout (s)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="compose ps + API health").set_defaults(func=cmd_status)
    sub.add_parser("health", help="deep API health (exit 1 on failure)").set_defaults(func=cmd_health)

    pr = sub.add_parser("run", help="run arbitrary command in remote root")
    pr.add_argument("cmd", nargs=argparse.REMAINDER)
    pr.set_defaults(func=cmd_run)

    pc = sub.add_parser("compose", help="docker compose passthrough")
    pc.add_argument("args", nargs=argparse.REMAINDER)
    pc.set_defaults(func=cmd_compose)

    pa = sub.add_parser("api-exec", help="exec command inside api container")
    pa.add_argument("cmd", nargs=argparse.REMAINDER)
    pa.set_defaults(func=cmd_api_exec)

    pq = sub.add_parser("psql", help="run SQL inside postgres container")
    pq.add_argument("sql", nargs=argparse.REMAINDER)
    pq.set_defaults(func=cmd_psql)

    pm = sub.add_parser("migrate", help="run DB migration runner inside api")
    pm.add_argument("action", choices=["status", "apply", "check", "baseline"], default="status", nargs="?")
    pm.set_defaults(func=cmd_migrate)

    pms = sub.add_parser("meili-sync", help="sync Meilisearch (secrets from container env)")
    pms.add_argument("--preflight-gate", action="store_true")
    pms.set_defaults(func=cmd_meili_sync)

    sub.add_parser("rebuild-web", help="rebuild + restart web service").set_defaults(func=cmd_rebuild_web)

    pd = sub.add_parser("deploy", help="git pull + rebuild web + migrate apply/check")
    pd.add_argument("--skip-migrate", action="store_true")
    pd.set_defaults(func=cmd_deploy)

    pt = sub.add_parser("tail", help="tail a remote log file")
    pt.add_argument("path")
    pt.add_argument("-n", "--lines", type=int, default=40)
    pt.set_defaults(func=cmd_tail)

    pu = sub.add_parser("upload", help="sftp upload a local file")
    pu.add_argument("local")
    pu.add_argument("remote")
    pu.set_defaults(func=cmd_upload)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
