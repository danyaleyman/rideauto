"""Стабильная инвалидация JSON-кэша каталога без SCAN Redis (блок J+K)."""

from __future__ import annotations

from typing import Dict, Tuple

from fastapi_app.config import Settings


def cache_epoch_value(settings: Settings) -> str:
    raw = str(getattr(settings, "catalog_cache_epoch", "") or "").strip()
    return raw if raw else "0"


def with_cache_epoch_dict(flat: Dict[str, str], settings: Settings) -> Dict[str, str]:
    out = dict(flat)
    out["__wra_cache_epoch__"] = cache_epoch_value(settings)
    return out


def with_cache_epoch_tuple(
    flat: Tuple[Tuple[str, str], ...],
    settings: Settings,
) -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted((*flat, ("__wra_cache_epoch__", cache_epoch_value(settings)))))
