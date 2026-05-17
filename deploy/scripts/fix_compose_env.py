#!/usr/bin/env python3
"""
Нормализует /opt/rideauto/.env для Docker Compose:
- WRA_PG_DSN, WRA_MEILISEARCH_URL, WRA_REDIS_URL, WRA_API_INTERNAL — имена сервисов compose
- DATABASE_URL — 127.0.0.1 для скриптов на хосте VPS (отдельно от WRA_PG_DSN)
"""
from __future__ import annotations

import re
import shutil
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

COMPOSE_KEYS: dict[str, str] = {
    "WRA_PG_DSN": "",  # filled below
    "WRA_MEILISEARCH_URL": "http://meilisearch:7700",
    "WRA_REDIS_URL": "redis://redis:6379/0",
    "WRA_API_INTERNAL": "http://api:8080",
}

MARKER = "# --- RideAuto Compose (docker internal hosts) ---"


def _parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip()
    return out


def _format_env(lines: list[str]) -> str:
    body = "\n".join(lines).rstrip() + "\n"
    return body


def _dsn(user: str, password: str, host: str, port: int, db: str) -> str:
    u = urllib.parse.quote(user, safe="")
    p = urllib.parse.quote(password, safe="")
    return f"postgresql://{u}:{p}@{host}:{port}/{db.lstrip('/')}"


def _credentials_from_dsn(dsn: str) -> tuple[str, str, str, int] | None:
    if not dsn:
        return None
    p = urllib.parse.urlsplit(dsn)
    if not p.username:
        return None
    user = urllib.parse.unquote(p.username)
    password = urllib.parse.unquote(p.password or "")
    db = (p.path or "/wra").lstrip("/") or "wra"
    port = p.port or 5432
    return user, password, db, port


def _upsert(lines: list[str], key: str, value: str) -> list[str]:
    pat = re.compile(rf"^\s*{re.escape(key)}\s*=")
    replaced = False
    out: list[str] = []
    for line in lines:
        if pat.match(line):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    return out


def main() -> int:
    if not ENV_PATH.is_file():
        print(f"Missing {ENV_PATH}", file=sys.stderr)
        return 1

    backup = ENV_PATH.with_suffix(".env.bak")
    shutil.copy2(ENV_PATH, backup)
    print(f"Backup: {backup}")

    raw = ENV_PATH.read_text(encoding="utf-8")
    lines = raw.splitlines()
    env = _parse_env(raw)

    creds = None
    for key in ("WRA_PG_DSN", "DATABASE_URL", "SYNC_PG_DSN"):
        creds = _credentials_from_dsn(env.get(key, ""))
        if creds:
            break
    if not creds:
        user = env.get("POSTGRES_USER", "wra")
        password = env.get("POSTGRES_PASSWORD", "wra")
        db = env.get("POSTGRES_DB", "wra")
        port = int(env.get("POSTGRES_PORT", "5432") or "5432")
        creds = (user, password, db, port)

    user, password, db, port = creds
    compose_dsn = _dsn(user, password, "postgres", port, db)
    host_dsn = _dsn(user, password, "127.0.0.1", port, db)

    COMPOSE_KEYS["WRA_PG_DSN"] = compose_dsn

    if MARKER not in raw:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(MARKER)
        lines.append("# WRA_* ниже — для контейнеров api/web (хосты postgres, redis, meilisearch, api).")
        lines.append("# DATABASE_URL — только для скриптов на хосте VPS (127.0.0.1).")

    for key, val in COMPOSE_KEYS.items():
        old = env.get(key, "")
        if old != val:
            print(f"  {key}: {old or '(unset)'} -> (compose service host)")
        lines = _upsert(lines, key, val)

    old_db = env.get("DATABASE_URL", "")
    if old_db != host_dsn:
        print(f"  DATABASE_URL: set for host scripts @127.0.0.1")
    lines = _upsert(lines, "DATABASE_URL", host_dsn)

    ENV_PATH.write_text(_format_env(lines), encoding="utf-8")
    print(f"Updated {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
