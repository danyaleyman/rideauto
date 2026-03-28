#!/usr/bin/env python3
"""
Run subscription notifications via API endpoint.

Usage:
  python backend/scripts/run_subscription_notifications.py --api http://127.0.0.1:8080 --admin-key YOUR_KEY
"""
from __future__ import annotations

import argparse
import json
import sys

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Run subscription notifications")
    parser.add_argument("--api", default="http://127.0.0.1:8080", help="API base URL")
    parser.add_argument("--admin-key", required=True, help="Admin key for notifications endpoint")
    args = parser.parse_args()

    url = args.api.rstrip("/") + "/api/subscriptions/run-notifications"
    try:
        r = requests.post(url, headers={"X-Admin-Key": args.admin_key}, timeout=30)
        r.raise_for_status()
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(f"Failed to run notifications: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
