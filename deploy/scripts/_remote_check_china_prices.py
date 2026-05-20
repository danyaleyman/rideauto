#!/usr/bin/env python3
"""One-off: inspect Che168 price outliers on production."""
from __future__ import annotations

import sys

import paramiko


def main() -> int:
    pw = sys.argv[1] if len(sys.argv) > 1 else ""
    if not pw:
        print("usage: _remote_check_china_prices.py <password>", file=sys.stderr)
        return 2
    sql = (
        "SELECT car_id, "
        "COALESCE(data->'data'->>'price_cny',''), "
        "COALESCE(data->'data'->>'my_price',''), "
        "COALESCE(data->'data'->>'che168_price_cny_rule',''), "
        "COALESCE(data->'data'->>'che168_price_raw','') "
        "FROM cars WHERE lower(source)='che168' "
        "AND NULLIF(data->'data'->>'price_cny','')::numeric > 500000 "
        "ORDER BY NULLIF(data->'data'->>'price_cny','')::numeric DESC LIMIT 10;"
    )
    cmd = (
        f"cd /opt/rideauto && docker compose exec -T postgres "
        f"psql -U rideauto -d rideauto -t -A -F'|' -c {sql!r}"
    )
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("62.76.31.51", username="root", password=pw, timeout=30)
    _, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
    print(out or "(empty)")
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
