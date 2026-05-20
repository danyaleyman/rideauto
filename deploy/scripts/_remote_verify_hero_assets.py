#!/usr/bin/env python3
"""Проверка hero-ассетов на VPS. Usage: _remote_verify_hero_assets.py <password>"""
import sys

import paramiko

ASSETS = [
    "/opt/rideauto/web/public/assets/hero.glb",
    "/opt/rideauto/web/public/assets/hero-fallback-animation.webm",
    "/opt/rideauto/web/public/assets/hero-fallback-image.png",
]
CMD = (
    "set -e; "
    "echo '=== host public/assets ==='; "
    "ls -lh /opt/rideauto/web/public/assets/hero* 2>&1; "
    "echo '=== container public/assets ==='; "
    "docker compose -f /opt/rideauto/docker-compose.yml exec -T web "
    "ls -lh /app/public/assets/hero.glb /app/public/assets/hero-fallback-image.png 2>&1; "
    "echo '=== HTTP from container ==='; "
    "docker compose -f /opt/rideauto/docker-compose.yml exec -T web "
    "wget -q -S -O /dev/null http://127.0.0.1:3000/assets/hero.glb 2>&1 | head -5"
)


def main() -> int:
    pw = sys.argv[1]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("62.76.31.51", username="root", password=pw, timeout=30)
    _, stdout, stderr = c.exec_command(CMD, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
