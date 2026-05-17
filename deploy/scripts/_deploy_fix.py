#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

import paramiko

REPO = Path(__file__).resolve().parents[2]


def main() -> None:
    pw = os.environ["CHE168_DEPLOY_PASSWORD"]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("62.76.31.51", username="root", password=pw, timeout=25)

    def run(cmd: str, timeout: int = 180) -> str:
        _, o, e = c.exec_command(cmd, timeout=timeout)
        return (o.read() + e.read()).decode("utf-8", errors="replace").strip()

    sftp = c.open_sftp()
    src = REPO / "backend/scripts/fill_hp_catalog_deepseek.py"
    with sftp.file("/opt/rideauto/backend/scripts/fill_hp_catalog_deepseek.py", "wb") as f:
        f.write(src.read_bytes().replace(b"\r\n", b"\n"))
    sftp.close()
    print("uploaded fill script")

    run("screen -S hp-korea -X quit 2>/dev/null || true")
    time.sleep(2)
    run(
        "screen -dmS hp-korea bash -lc "
        "'bash /opt/rideauto/deploy/scripts/run_hp_catalog_korea_screen.sh'"
    )
    time.sleep(25)
    log = run("ls -t /opt/rideauto/logs/hp_catalog_korea_*.log 2>/dev/null | head -1")
    print("log:", log)
    if log:
        print(run(f"tail -n 15 {log}", timeout=60))
    c.close()


if __name__ == "__main__":
    main()
