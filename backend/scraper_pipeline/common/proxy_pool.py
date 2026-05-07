"""Shared proxy pool helpers for scraper clients."""

from __future__ import annotations

import random
from typing import List, Optional


class ProxyPool:
    def __init__(self, urls: List[str], *, rotation: str = "round_robin") -> None:
        self._urls = [str(u).strip() for u in (urls or []) if str(u).strip()]
        self._rotation = str(rotation or "round_robin").strip().lower()
        self._idx = -1

    @property
    def enabled(self) -> bool:
        return bool(self._urls)

    def all(self) -> List[str]:
        return list(self._urls)

    def next_url(self) -> Optional[str]:
        if not self._urls:
            return None
        if self._rotation == "random":
            return random.choice(self._urls)
        self._idx = (self._idx + 1) % len(self._urls)
        return self._urls[self._idx]
