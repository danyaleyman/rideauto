from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen


def _parse_images(raw: Any) -> List[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return [raw] if raw.startswith("http") else []
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        if isinstance(item, str) and item.startswith("http"):
            out.append(item)
        elif isinstance(item, dict):
            u = item.get("url") or item.get("imageUrl") or item.get("src")
            if isinstance(u, str) and u.startswith("http"):
                out.append(u)
    return out


def fetch_json(url: str) -> Dict[str, Any]:
    with urlopen(url, timeout=30) as r:  # nosec - internal operational script
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description="Audit china listing image counts from API")
    p.add_argument("--base", default="http://127.0.0.1:8080", help="API base")
    p.add_argument("--n", type=int, default=10, help="cars to check")
    args = p.parse_args()

    qs = urlencode({"region": "china", "page": 1, "per_page": args.n})
    url = f"{args.base.rstrip('/')}/api/cars?{qs}"
    payload = fetch_json(url)
    rows = payload.get("result") or []
    if not isinstance(rows, list):
        print("bad payload: result is not list")
        return 2

    print(f"Checked: {len(rows)} cars")
    ge2 = 0
    for car in rows:
        if not isinstance(car, dict):
            continue
        cid = str(car.get("id") or "")
        data = car.get("data") if isinstance(car.get("data"), dict) else {}
        imgs = _parse_images(data.get("images"))
        if len(imgs) >= 2:
            ge2 += 1
        print(f"{cid}: images={len(imgs)}")

    print(f"cars with >=2 images: {ge2}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

