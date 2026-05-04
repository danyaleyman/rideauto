"""Prometheus textfile (node_exporter) для che168_listing_live_checker."""
from __future__ import annotations

import time
from typing import Any, Dict


def write_che168_live_checker_prometheus_textfile(path: str, stats: Dict[str, Any]) -> None:
    if not path or not str(path).strip():
        return
    p = str(path).strip()
    lines = [
        "# HELP che168_live_checker_sold_total Listings marked sold this run",
        "# TYPE che168_live_checker_sold_total counter",
        f"che168_live_checker_sold_total {int(stats.get('sold', 0) or 0)}",
        "# HELP che168_live_checker_active_total Listings confirmed active this run",
        "# TYPE che168_live_checker_active_total counter",
        f"che168_live_checker_active_total {int(stats.get('active', 0) or 0)}",
        "# HELP che168_live_checker_skip_total Transient HTTP/skip this run",
        "# TYPE che168_live_checker_skip_total counter",
        f"che168_live_checker_skip_total {int(stats.get('skip', 0) or 0)}",
        "# HELP che168_live_checker_session_refreshes_total Playwright bootstrap due to session hint",
        "# TYPE che168_live_checker_session_refreshes_total counter",
        f"che168_live_checker_session_refreshes_total {int(stats.get('session_refreshes', 0) or 0)}",
        "# HELP che168_live_checker_last_run_unixtime Last batch completion",
        "# TYPE che168_live_checker_last_run_unixtime gauge",
        f"che168_live_checker_last_run_unixtime {int(time.time())}",
        "",
    ]
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
