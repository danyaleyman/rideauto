#!/usr/bin/env python3
"""
Для процессов на хост-сервере: hostname postgres (compose DNS) недоступен.
Замена на 127.0.0.1 с сохранением user/password/port/path/query.

stdin: если argv пустой — одна строка DSN без завершающего \\n.
"""
from __future__ import annotations

import sys
import urllib.parse


def rewrite_if_postgres_hostname(dsn: str) -> tuple[str, bool]:
    s = (dsn or "").strip()
    p = urllib.parse.urlsplit(s)
    if not p.scheme or not p.hostname or str(p.hostname).lower() != "postgres":
        return s, False
    port = p.port if p.port is not None else 5432
    auth = ""
    if p.username:
        uq = urllib.parse.quote(p.username, safe="")
        if p.password is not None:
            uq += ":" + urllib.parse.quote(p.password, safe="")
        auth = uq + "@"
    netloc = f"{auth}127.0.0.1:{port}"
    return urllib.parse.urlunsplit((p.scheme, netloc, p.path, p.query, p.fragment)), True


def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    out, changed = rewrite_if_postgres_hostname(raw)
    sys.stdout.write(out)
    if changed:
        print(
            "pg_dsn_host_local_rewrite: postgres → 127.0.0.1 (ран на хосте, не в docker-сети)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
