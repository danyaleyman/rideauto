#!/usr/bin/env python3
"""One-off remote deploy (reads password from argv[1]). Do not commit."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "deploy/scripts/fix_compose_env.py",
    "deploy/scripts/server_compose_env_fix_and_deploy.sh",
]


def upload_lf(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    with sftp.file(remote, "wb") as f:
        f.write(data)


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
        print("usage: _remote_deploy_once.py <password>", file=sys.stderr)
        return 2
    pw = sys.argv[1]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("62.76.31.51", username="root", password=pw, timeout=30)
    sftp = client.open_sftp()
    for rel in FILES:
        upload_lf(sftp, ROOT / rel, f"/opt/rideauto/{rel}")
        print(f"uploaded {rel}")
    sftp.close()
    code = stream_exec(
        client,
        "cd /opt/rideauto && chmod +x deploy/scripts/server_compose_env_fix_and_deploy.sh "
        "&& bash deploy/scripts/server_compose_env_fix_and_deploy.sh",
    )
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
