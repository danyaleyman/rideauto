from __future__ import annotations

import hashlib
import os


def clean_read_mode_enabled(default: bool = False) -> bool:
    raw = str(os.environ.get("WRA_CLEAN_READ_MODE", "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def clean_read_rollout_percent(default: int = 100) -> int:
    raw = str(os.environ.get("WRA_CLEAN_READ_PERCENT", "")).strip()
    if not raw:
        return max(0, min(int(default), 100))
    try:
        return max(0, min(int(raw), 100))
    except ValueError:
        return max(0, min(int(default), 100))


def clean_read_enabled_for_key(key: str, *, default_enabled: bool = False) -> bool:
    if not clean_read_mode_enabled(default=default_enabled):
        return False
    pct = clean_read_rollout_percent(default=100)
    if pct >= 100:
        return True
    if pct <= 0:
        return False
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < pct


def legacy_fallbacks_enabled(default: bool = True) -> bool:
    raw = str(os.environ.get("WRA_LEGACY_FALLBACKS_ENABLED", "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}

