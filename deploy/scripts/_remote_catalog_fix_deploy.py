#!/usr/bin/env python3
"""Deploy catalog fixes + China price backfill on production VPS."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
HOST = "62.76.31.51"
USER = "root"

# Relative paths changed in this fix batch.
CHANGED_FILES = [
    "backend/fastapi_app/catalog_slim.py",
    "backend/scraper_pipeline/che168/parser.py",
    "web/src/lib/china-options-display.ts",
    "web/src/lib/catalog-client-utils.ts",
    "web/src/components/catalog/CatalogClient.tsx",
    "web/src/components/car/CarDetailAccordions.tsx",
    "web/src/app/car/[ref]/page.tsx",
]


def upload_lf(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    remote_dir = "/".join(remote.split("/")[:-1])
    try:
        sftp.stat(remote_dir)
    except OSError:
        parts = remote_dir.split("/")
        cur = ""
        for p in parts:
            if not p:
                continue
            cur = f"{cur}/{p}" if cur else p
            try:
                sftp.stat(cur)
            except OSError:
                sftp.mkdir(cur)
    with sftp.file(remote, "wb") as f:
        f.write(data)


def stream_exec(client: paramiko.SSHClient, cmd: str, timeout: int = 7200) -> int:
    print(f"\n>>> {cmd}\n", flush=True)
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    chan = stdout.channel
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65535).decode("utf-8", errors="replace")
            try:
                sys.stdout.write(chunk)
            except UnicodeEncodeError:
                sys.stdout.buffer.write(chunk.encode("utf-8", errors="replace"))
            sys.stdout.flush()
        if chan.exit_status_ready():
            while chan.recv_ready():
                chunk = chan.recv(65535).decode("utf-8", errors="replace")
                try:
                    sys.stdout.write(chunk)
                except UnicodeEncodeError:
                    sys.stdout.buffer.write(chunk.encode("utf-8", errors="replace"))
            break
        time.sleep(0.4)
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write(err)
    return int(chan.recv_exit_status())


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _remote_catalog_fix_deploy.py <password>", file=sys.stderr)
        return 2
    pw = sys.argv[1]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=pw, timeout=30)
    sftp = client.open_sftp()
    for rel in CHANGED_FILES:
        local = ROOT / rel
        remote = f"/opt/rideauto/{rel.replace(chr(92), '/')}"
        if not local.is_file():
            print(f"skip missing {local}", file=sys.stderr)
            continue
        upload_lf(sftp, local, remote)
        print(f"uploaded {rel}")
    sftp.close()

    steps = [
        "cd /opt/rideauto && docker compose build api web 2>&1 | tail -35",
        "cd /opt/rideauto && docker compose up -d api web 2>&1",
        "curl -sS 'http://127.0.0.1:8000/api/search?region=korea&source=encar&sort=date_new&limit=3' | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(x.get('id'), x.get('catalog_created_at')) for x in d.get('result',[])]\"",
    ]
    rc = 0
    for cmd in steps:
        code = stream_exec(client, cmd)
        if code != 0 and "curl" not in cmd:
            rc = code
            print(f"step failed exit={code}", file=sys.stderr)
    client.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
