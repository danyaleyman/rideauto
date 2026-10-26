#!/usr/bin/env python3
"""Один тик автопостинга в Telegram-канал (1 лот, если дневной лимит не исчерпан).

Usage:
  python backend/scripts/run_telegram_channel_autopost.py --api http://127.0.0.1:8080 --admin-key YOUR_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish one advantageous listing to the Telegram channel")
    parser.add_argument("--api", default="http://127.0.0.1:8080", help="API base URL")
    parser.add_argument(
        "--admin-key",
        default=os.environ.get("WRA_SUBSCRIPTIONS_ADMIN_KEY")
        or os.environ.get("SUBSCRIPTIONS_ADMIN_KEY")
        or "",
        help="WRA_SUBSCRIPTIONS_ADMIN_KEY / cache invalidate secret",
    )
    parser.add_argument("--limit", type=int, default=1, help="How many posts this tick (1–8)")
    parser.add_argument(
        "--ignore-daily-limit",
        action="store_true",
        help="Ignore 2+2 daily quota (manual batch)",
    )
    args = parser.parse_args()
    if not args.admin_key:
        print("admin key required (--admin-key or SUBSCRIPTIONS_ADMIN_KEY)", file=sys.stderr)
        return 2

    url = args.api.rstrip("/") + "/api/telegram/channel/autopost"
    try:
        r = requests.post(
            url,
            headers={"X-Admin-Key": args.admin_key, "Content-Type": "application/json"},
            json={
                "limit": max(1, min(8, int(args.limit))),
                "ignore_daily_limit": bool(args.ignore_daily_limit),
            },
            timeout=420,
        )
        r.raise_for_status()
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(f"Failed to run telegram autopost: {e}", file=sys.stderr)
        if getattr(e, "response", None) is not None:
            print(getattr(e.response, "text", ""), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
