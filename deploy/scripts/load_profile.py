#!/usr/bin/env python3
"""
Sprint B load profile for API endpoints.

Usage:
  python3 deploy/scripts/load_profile.py \
    --base-url http://127.0.0.1:8080 \
    --car-id dongchedi-23175150
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class Scenario:
    name: str
    rps: int
    seconds: int


SCENARIOS = [
    Scenario(name="warmup", rps=20, seconds=20),
    Scenario(name="rps-50", rps=50, seconds=60),
    Scenario(name="rps-100", rps=100, seconds=60),
    Scenario(name="rps-200", rps=200, seconds=60),
]


def pct(sorted_values: List[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    i = (len(sorted_values) - 1) * p
    lo = math.floor(i)
    hi = math.ceil(i)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (i - lo)


def worker(base_url: str, car_id: str, stop_at: float, rps: int, out: List[Tuple[float, int]], lock: threading.Lock) -> None:
    search_url = f"{base_url}/api/search?per_page=12&source=encar&sort=date_new"
    car_url = f"{base_url}/api/car/{car_id}"
    timeout = 10.0
    interval = 1.0 / max(1, rps)
    next_tick = time.perf_counter()
    while time.perf_counter() < stop_at:
        target = search_url if random.random() < 0.75 else car_url
        t0 = time.perf_counter()
        status = 0
        try:
            req = urllib.request.Request(target, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _ = resp.read(128)
                status = int(resp.status)
        except urllib.error.HTTPError as e:
            status = int(e.code)
        except Exception:
            status = 0
        dt_ms = (time.perf_counter() - t0) * 1000.0
        with lock:
            out.append((dt_ms, status))
        next_tick += interval
        sleep_for = next_tick - time.perf_counter()
        if sleep_for > 0:
            time.sleep(sleep_for)


def run_scenario(base_url: str, car_id: str, scenario: Scenario) -> Dict[str, float]:
    threads: List[threading.Thread] = []
    data: List[Tuple[float, int]] = []
    lock = threading.Lock()
    # Use 10 workers to smooth scheduling jitter.
    workers = 10
    stop_at = time.perf_counter() + scenario.seconds
    rps_per_worker = max(1, scenario.rps // workers)
    for _ in range(workers):
        t = threading.Thread(
            target=worker,
            args=(base_url, car_id, stop_at, rps_per_worker, data, lock),
            daemon=True,
        )
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    lat = sorted([x[0] for x in data])
    statuses = [x[1] for x in data]
    total = len(statuses)
    ok = sum(1 for s in statuses if 200 <= s < 400)
    err5xx = sum(1 for s in statuses if 500 <= s < 600)
    err4xx = sum(1 for s in statuses if 400 <= s < 500)
    net = sum(1 for s in statuses if s == 0)
    return {
        "requests": float(total),
        "ok_rate": (ok / total * 100.0) if total else 0.0,
        "err_5xx_rate": (err5xx / total * 100.0) if total else 0.0,
        "err_4xx_rate": (err4xx / total * 100.0) if total else 0.0,
        "net_err_rate": (net / total * 100.0) if total else 0.0,
        "mean_ms": statistics.fmean(lat) if lat else 0.0,
        "p50_ms": pct(lat, 0.50),
        "p95_ms": pct(lat, 0.95),
        "p99_ms": pct(lat, 0.99),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Run pragmatic load profile for /api/search and /api/car.")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--car-id", required=True, help="Existing car_id for /api/car/{id} checks")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    print(f"load profile base_url={base} car_id={args.car_id}", flush=True)
    results: Dict[str, Dict[str, float]] = {}
    for sc in SCENARIOS:
        print(f"\n==> scenario {sc.name} rps={sc.rps} duration={sc.seconds}s", flush=True)
        metrics = run_scenario(base, args.car_id, sc)
        results[sc.name] = metrics
        print(json.dumps(metrics, ensure_ascii=True, indent=2), flush=True)

    print("\n==> summary", flush=True)
    print(json.dumps(results, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
