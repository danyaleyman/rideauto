#!/usr/bin/env python3
import sys
import time
import paramiko

pw = sys.argv[1]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("62.76.31.51", username="root", password=pw, timeout=30)
_, stdout, stderr = c.exec_command(
    "cd /opt/rideauto && docker compose build web 2>&1 && "
    "docker compose up -d --no-deps web 2>&1 && docker compose ps web 2>&1",
    get_pty=False,
)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
code = stdout.channel.recv_exit_status()
Path = __import__("pathlib").Path
Path(__file__).resolve().parents[1].joinpath("_rebuild.log").write_text(out + "\n" + err, encoding="utf-8")
print("exit", code)
c.close()
sys.exit(code)
