#!/usr/bin/env python3
"""Прогрев in-memory кэша фасетов и страниц каталога /api/search (после рестарта API или деплоя).

  curl не обязателен: только stdlib.
  python scripts/warm_public_cache.py --base https://rideauto.ru
  python scripts/warm_public_cache.py --base http://127.0.0.1:8080
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def _encode_offset_cursor(offset: int, limit: int) -> str:
    payload = {"v": 1, "o": int(offset), "l": int(limit)}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _get(url: str, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.geturl()
    except urllib.error.HTTPError as e:
        return int(e.code), url


def main() -> int:
    p = argparse.ArgumentParser(description="GET /api/facets и /api/search для прогрева кэша воркера")
    p.add_argument("--base", default="http://127.0.0.1:8080", help="Origin API (без хвостового /)")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument(
        "--pages",
        type=int,
        default=5,
        help="Сколько страниц каталога прогреть на каждый рынок (offset через cursor)",
    )
    args = p.parse_args()
    base = args.base.rstrip("/")
    per_page = 10
    paths = [
        "/api/facets?source=encar",
        "/api/facets?region=china&source=china",
    ]
    # Синхронно с web/src/lib/catalog-url.ts: Korea / China и постраничный cursor.
    for region, source in (("korea", "encar"), ("china", "che168")):
        for page in range(1, max(1, args.pages) + 1):
            offset = (page - 1) * per_page
            cur = urllib.parse.quote(_encode_offset_cursor(offset, per_page), safe="")
            q = f"region={region}&source={source}&per_page={per_page}"
            if page > 1:
                q += f"&cursor={cur}"
            paths.append(f"/api/search?{q}")
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
