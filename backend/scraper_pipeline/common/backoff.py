"""Shared backoff profile builders for scraper clients."""

from __future__ import annotations

from typing import Any, Dict

from scraper_pipeline.retry import BackoffConfig


def build_backoff_config(global_cfg: Dict[str, Any], local_retry_cfg: Dict[str, Any]) -> BackoffConfig:
    g = global_cfg or {}
    r = local_retry_cfg or {}
    base = float(r.get("backoff_base", g.get("backoff_base", 1)) or 1)
    cap = float(r.get("backoff_max", g.get("backoff_max", 60)) or 60)
    jitter_enabled = bool(r.get("jitter", g.get("jitter", False)))
    if jitter_enabled:
        j_min = float(r.get("jitter_min", g.get("jitter_min", 0.0)) or 0.0)
        j_max = float(r.get("jitter_max", g.get("jitter_max", 0.5)) or 0.5)
    else:
        j_min = 0.0
        j_max = 0.0
    return BackoffConfig(base_sec=base, max_sec=cap, jitter_min=j_min, jitter_max=j_max)
