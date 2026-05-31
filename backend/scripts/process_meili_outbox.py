#!/usr/bin/env python3
"""Process meili_sync_outbox via API or direct pool."""
from __future__ import annotations

import argparse
import json
import sys

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Process Meili sync outbox")
    parser.add_argument("--api", default="http://127.0.0.1:8080", help="API base URL")
    parser.add_argument("--admin-key", required=True, help="X-Admin-Key")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    url = args.api.rstrip("/") + f"/api/meili/outbox/process?limit={args.limit}"
    try:
        r = requests.post(url, headers={"X-Admin-Key": args.admin_key}, timeout=120)
        r.raise_for_status()
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
