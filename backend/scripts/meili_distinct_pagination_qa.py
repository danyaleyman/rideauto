#!/usr/bin/env python3
"""Acceptance: Meilisearch pagination + estimatedTotalHits with distinctAttribute.

Example:
  python scripts/meili_distinct_pagination_qa.py --meili-url http://127.0.0.1:7700 --pages 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Set


def _search(url: str, key: str, index: str, offset: int, limit: int, q: str = "") -> Dict[str, Any]:
    endpoint = url.rstrip("/") + f"/indexes/{index}/search"
    body = json.dumps({"q": q, "offset": offset, "limit": limit}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meili-url", default=os.environ.get("WRA_MEILISEARCH_URL", "http://127.0.0.1:7700"))
    ap.add_argument("--meili-key", default=os.environ.get("MEILI_MASTER_KEY") or os.environ.get("WRA_MEILISEARCH_KEY") or "")
    ap.add_argument("--index", default=os.environ.get("WRA_MEILI_LIVE_INDEX", "cars"))
    ap.add_argument("--page-size", type=int, default=20)
    ap.add_argument("--pages", type=int, default=5)
    ap.add_argument("--q", default="")
    args = ap.parse_args()

    seen: Set[str] = set()
    dups = 0
    totals: List[Any] = []
    for i in range(args.pages):
        offset = i * args.page_size
        data = _search(args.meili_url, args.meili_key, args.index, offset, args.page_size, args.q)
        hits = data.get("hits") or []
        est = data.get("estimatedTotalHits", data.get("totalHits"))
        totals.append(est)
        for h in hits:
            if not isinstance(h, dict):
                continue
            cid = str(h.get("id") or h.get("car_id") or "")
            key = str(h.get("catalog_dedupe_key") or cid)
            if key in seen:
                dups += 1
            seen.add(key)
        print(f"page={i+1} offset={offset} hits={len(hits)} estimatedTotalHits={est}", flush=True)

    ok = dups == 0 and len(seen) > 0
    print(
        json.dumps(
            {
                "ok": ok,
                "unique_keys": len(seen),
                "cross_page_duplicate_keys": dups,
                "estimated_totals": totals,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
