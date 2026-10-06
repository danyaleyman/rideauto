#!/usr/bin/env python3
"""PD retention purge for leads / auth tokens / sessions.

Defaults (ops; keep in sync with privacy copy + /etc/default/rideauto):
  WRA_PD_LEAD_RETENTION_DAYS=365
  WRA_PD_MAGIC_TOKEN_RETENTION_DAYS=7
  WRA_PD_SESSION_RETENTION_DAYS=90

Example:
  python scripts/pd_retention_purge.py --dsn "$DATABASE_URL"           # dry-run
  python scripts/pd_retention_purge.py --dsn "$DATABASE_URL" --apply
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict

try:
    import psycopg2
except ImportError:
    print("Install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--lead-days", type=int, default=0)
    ap.add_argument("--magic-days", type=int, default=0)
    ap.add_argument("--session-days", type=int, default=0)
    args = ap.parse_args()
    apply = args.apply or (
        os.environ.get("WRA_PD_PURGE_APPLY", "").strip().lower() in {"1", "true", "yes"}
    )
    dsn = (args.dsn or "").strip() or os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("need --dsn or DATABASE_URL", file=sys.stderr)
        return 2

    lead_d = args.lead_days or _int_env("WRA_PD_LEAD_RETENTION_DAYS", 365)
    magic_d = args.magic_days or _int_env("WRA_PD_MAGIC_TOKEN_RETENTION_DAYS", 7)
    sess_d = args.session_days or _int_env("WRA_PD_SESSION_RETENTION_DAYS", 90)

    counts: Dict[str, int] = {}
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM lead_requests WHERE created_at < NOW() - (%s || ' days')::interval",
                (str(lead_d),),
            )
            counts["leads_expired"] = int(cur.fetchone()[0] or 0)
            if apply and counts["leads_expired"]:
                cur.execute(
                    "DELETE FROM lead_requests WHERE created_at < NOW() - (%s || ' days')::interval",
                    (str(lead_d),),
                )
                counts["leads_deleted"] = int(cur.rowcount)

            # Used or long-expired magic tokens
            cur.execute(
                """
                SELECT COUNT(*) FROM auth_magic_tokens
                WHERE used_at IS NOT NULL
                   OR expires_at < NOW() - (%s || ' days')::interval
                   OR created_at < NOW() - (%s || ' days')::interval
                """,
                (str(magic_d), str(magic_d)),
            )
            counts["magic_expired"] = int(cur.fetchone()[0] or 0)
            if apply and counts["magic_expired"]:
                cur.execute(
                    """
                    DELETE FROM auth_magic_tokens
                    WHERE used_at IS NOT NULL
                       OR expires_at < NOW() - (%s || ' days')::interval
                       OR created_at < NOW() - (%s || ' days')::interval
                    """,
                    (str(magic_d), str(magic_d)),
                )
                counts["magic_deleted"] = int(cur.rowcount)

            cur.execute(
                """
                SELECT COUNT(*) FROM auth_sessions
                WHERE revoked_at IS NOT NULL
                   OR expires_at < NOW()
                   OR created_at < NOW() - (%s || ' days')::interval
                """,
                (str(sess_d),),
            )
            counts["sessions_expired"] = int(cur.fetchone()[0] or 0)
            if apply and counts["sessions_expired"]:
                cur.execute(
                    """
                    DELETE FROM auth_sessions
                    WHERE revoked_at IS NOT NULL
                       OR expires_at < NOW()
                       OR created_at < NOW() - (%s || ' days')::interval
                    """,
                    (str(sess_d),),
                )
                counts["sessions_deleted"] = int(cur.rowcount)

            if apply:
                conn.commit()
            else:
                conn.rollback()
    finally:
        conn.close()

    print(
        f"pd_retention: apply={apply} lead_days={lead_d} magic_days={magic_d} "
        f"session_days={sess_d} counts={counts}",
        flush=True,
    )

    textfile = (os.environ.get("WRA_PD_PURGE_TEXTFILE") or "").strip()
    if textfile:
        lines = [
            "# HELP wra_pd_purge_leads_expired Leads older than retention",
            "# TYPE wra_pd_purge_leads_expired gauge",
            f"wra_pd_purge_leads_expired {counts.get('leads_expired', 0)}",
            "# HELP wra_pd_purge_magic_expired Magic tokens eligible for purge",
            "# TYPE wra_pd_purge_magic_expired gauge",
            f"wra_pd_purge_magic_expired {counts.get('magic_expired', 0)}",
            "# HELP wra_pd_purge_sessions_expired Sessions eligible for purge",
            "# TYPE wra_pd_purge_sessions_expired gauge",
            f"wra_pd_purge_sessions_expired {counts.get('sessions_expired', 0)}",
            "# HELP wra_pd_purge_last_unixtime Last purge run",
            "# TYPE wra_pd_purge_last_unixtime gauge",
            f"wra_pd_purge_last_unixtime {int(time.time())}",
            "",
        ]
        out = Path(textfile)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text("\n".join(lines), encoding="utf-8")
        tmp.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
