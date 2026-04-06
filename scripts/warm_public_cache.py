#!/usr/bin/env python3
"""Прогрев in-memory кэша фасетов и первой страницы каталога (после рестарта API или деплоя).

  curl не обязателен: только stdlib.
  python scripts/warm_public_cache.py --base https://rideauto.ru
  python scripts/warm_public_cache.py --base http://127.0.0.1:8080
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def _get(url: str, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.geturl()
    except urllib.error.HTTPError as e:
        return int(e.code), url


def main() -> int:
    p = argparse.ArgumentParser(description="GET /api/facets и /api/cars для прогрева кэша воркера")
    p.add_argument("--base", default="http://127.0.0.1:8080", help="Origin API (без хвостового /)")
    p.add_argument("--timeout", type=float, default=120.0)
    args = p.parse_args()
    base = args.base.rstrip("/")
    paths = [
        "/api/facets?source=encar",
        "/api/facets?region=china&source=china",
        "/api/cars?page=1&per_page=12&source=encar",
        "/api/cars?page=1&per_page=12&region=china",
    ]
    bad = 0
    for path in paths:
        url = base + path
        code, _ = _get(url, args.timeout)
        print(f"{code}\t{url}")
        if code != 200:
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
