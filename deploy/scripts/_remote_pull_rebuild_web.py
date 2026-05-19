#!/usr/bin/env python3
"""git pull + rebuild web on VPS. Usage: _remote_pull_rebuild_web.py <password>"""
import sys
from pathlib import Path

import paramiko

pw = sys.argv[1]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("62.76.31.51", username="root", password=pw, timeout=30)
_, stdout, _ = c.exec_command(
    "cd /opt/rideauto && git pull origin main 2>&1 && "
    "docker compose build web 2>&1 && "
    "docker compose up -d --no-deps web 2>&1 && "
    "docker compose ps web 2>&1",
    get_pty=False,
)
out = stdout.read().decode("utf-8", errors="replace")
code = stdout.channel.recv_exit_status()
log = Path(__file__).resolve().parents[1] / "_pull_rebuild.log"
log.write_text(out, encoding="utf-8")
print("exit", code)
print(out[-2000:] if len(out) > 2000 else out)
c.close()
sys.exit(code)
