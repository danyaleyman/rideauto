#!/usr/bin/env python3
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "web/src/components/home/ModelMediaCascade.tsx",
    "web/src/components/home/MarketModelViewer.tsx",
    "web/src/components/home/HomeLanding.tsx",
    "web/src/lib/preload-landing-models.ts",
]


def upload_lf(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    with sftp.file(remote, "wb") as f:
        f.write(data)


def main() -> int:
    pw = sys.argv[1]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("62.76.31.51", username="root", password=pw, timeout=30)
    sftp = c.open_sftp()
    for rel in FILES:
        upload_lf(sftp, ROOT / rel, f"/opt/rideauto/{rel}")
        print("uploaded", rel)
    sftp.close()
    _, stdout, _ = c.exec_command(
        "cd /opt/rideauto && docker compose build web && docker compose up -d --no-deps web",
        get_pty=False,
    )
    out = stdout.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    Path(__file__).resolve().parents[1].joinpath("_hero_fix_deploy.log").write_text(out, encoding="utf-8")
    print("exit", code)
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
