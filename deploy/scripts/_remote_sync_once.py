#!/usr/bin/env python3
"""One-off remote sync. Do not commit credentials."""
import os
import sys

import paramiko

HOST = "62.76.31.51"
USER = "root"
BUNDLE = os.path.join(os.environ.get("TEMP", "/tmp"), "rideauto.bundle")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _remote_sync_once.py <password>", file=sys.stderr)
        return 1
    pw = sys.argv[1]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=pw, timeout=30)
    sftp = client.open_sftp()
    sftp.put(BUNDLE, "/tmp/rideauto.bundle")
    sftp.close()
    script = """set -euo pipefail
cd /opt/rideauto
git fetch /tmp/rideauto.bundle main:bundle-main
git reset --hard bundle-main
python3 deploy/scripts/fix_compose_env.py
docker compose build --no-cache web
docker compose up -d --no-deps web
sleep 5
docker compose ps web api
curl -sS -o /dev/null -w 'home:%{http_code}\\n' http://127.0.0.1:8080/
curl -sS http://127.0.0.1:8080/api/health
"""
    import base64

    b64 = base64.b64encode(script.encode()).decode()
    _, stdout, stderr = client.exec_command(
        f"bash -lc 'echo {b64} | base64 -d | bash'", timeout=900
    )
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out)
    if err:
        print("STDERR:", err[-4000:], file=sys.stderr)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
