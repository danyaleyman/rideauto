#!/usr/bin/env python3
"""Finish deploy: web rebuild + price backfill with proper env."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[2]

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def upload_lf(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    with sftp.file(remote, "wb") as f:
        f.write(data)


def stream_exec(client: paramiko.SSHClient, cmd: str) -> int:
    print(f"\n>>> {cmd}\n", flush=True)
    _, stdout, _ = client.exec_command(cmd, get_pty=True, timeout=7200)
    chan = stdout.channel
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65535).decode("utf-8", errors="replace")
            sys.stdout.write(chunk)
            sys.stdout.flush()
        if chan.exit_status_ready():
            while chan.recv_ready():
                sys.stdout.write(chan.recv(65535).decode("utf-8", errors="replace"))
            break
        time.sleep(0.5)
    return int(chan.recv_exit_status())


def main() -> int:
    pw = sys.argv[1]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("62.76.31.51", username="root", password=pw, timeout=30)
    sftp = c.open_sftp()
    rel = "web/src/app/car/[ref]/page.tsx"
    upload_lf(sftp, ROOT / rel, f"/opt/rideauto/{rel}")
    sftp.close()
    print("uploaded page.tsx fix")

    cmds = [
        "cd /opt/rideauto && docker compose build web 2>&1 | tail -30",
        "cd /opt/rideauto && docker compose up -d --no-deps web 2>&1",
        (
            "set -a && source /etc/default/rideauto && set +a && "
            "cd /opt/rideauto && source .venv/bin/activate && "
            "export PYTHONPATH=/opt/rideauto/backend && "
            "python backend/scripts/backfill_che168_price_cny.py --apply 2>&1 | tail -25"
        ),
        (
            "set -a && source /etc/default/rideauto && set +a && "
            "sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_postgres_catalog_sync_host.sh --no-meilisearch 2>&1 | tail -25"
        ),
        "sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_meilisearch_sync_host.sh 2>&1 | tail -20",
        "curl -sS 'http://127.0.0.1:8000/api/search?region=china&source=che168&sort=price_high&limit=3' | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(x.get('id'),x.get('price')) for x in d.get('result',[])]\"",
    ]
    rc = 0
    for cmd in cmds:
        if stream_exec(c, cmd) != 0:
            rc = 1
    c.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
