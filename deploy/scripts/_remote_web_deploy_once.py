#!/usr/bin/env python3
"""Remote: git pull + rebuild web only. Usage: _remote_web_deploy_once.py <password>"""
from __future__ import annotations

import sys
import time

import paramiko


def stream_exec(client: paramiko.SSHClient, cmd: str) -> int:
    _, stdout, _ = client.exec_command(cmd, get_pty=True)
    chan = stdout.channel
    while True:
        if chan.recv_ready():
            sys.stdout.write(chan.recv(65535).decode("utf-8", errors="replace"))
            sys.stdout.flush()
        if chan.exit_status_ready():
            while chan.recv_ready():
                sys.stdout.write(chan.recv(65535).decode("utf-8", errors="replace"))
            break
        time.sleep(0.5)
    return int(chan.recv_exit_status())


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _remote_web_deploy_once.py <password>", file=sys.stderr)
        return 2
    pw = sys.argv[1]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("62.76.31.51", username="root", password=pw, timeout=30)
    cmd = (
        "cd /opt/rideauto && git pull && "
        "docker compose build web && "
        "docker compose up -d --no-deps web && "
        "docker compose ps web && "
        "docker compose exec -T web ls -la /app/public/assets/hero.glb"
    )
    code = stream_exec(client, cmd)
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
