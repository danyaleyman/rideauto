"""Shared proxy pool helpers for scraper clients."""

from __future__ import annotations

import random
import time
from typing import Callable, Dict, List, Optional


class ProxyPool:
    """Round-robin/random список прокси + health-quarantine мёртвых URL.

    Зачем quarantine (прод-инцидент Encar 2026-10-10): один мёртвый прокси держал слот до
    transport-cap (`curl: (28) ... 35000 ms`), 24 detail-воркера крутили `pop → fail → requeue`,
    общий circuit breaker открылся на 90 с (`detail_fail=650`, `cb_short=690`). Причина не в
    backoff: round-robin возвращал мёртвый URL каждому третьему воркеру и пул не помнил ошибок.

    Теперь после `failure_threshold` подряд connect-ошибок URL уходит в карантин на
    `quarantine_sec` и не выдаётся, пока есть живые. Если в карантине все — отдаём того, у кого
    он истекает раньше (лучше попытка, чем None и простой). `failure_threshold = 0` (дефолт)
    выключает поведение — пул работает как раньше.
    """

    def __init__(
        self,
        urls: List[str],
        *,
        rotation: str = "round_robin",
        failure_threshold: int = 0,
        quarantine_sec: float = 0.0,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._urls = [str(u).strip() for u in (urls or []) if str(u).strip()]
        self._rotation = str(rotation or "round_robin").strip().lower()
        self._idx = -1
        self._failure_threshold = max(0, int(failure_threshold or 0))
        self._quarantine_sec = max(0.0, float(quarantine_sec or 0.0))
        self._clock: Callable[[], float] = clock or time.monotonic
        self._fail_streak: Dict[str, int] = {}
        self._quarantine_until: Dict[str, float] = {}
        self.quarantine_events = 0
        self.quarantine_skips = 0

    @property
    def enabled(self) -> bool:
        return bool(self._urls)

    def all(self) -> List[str]:
        return list(self._urls)

    @property
    def health_enabled(self) -> bool:
        return self._failure_threshold > 0 and self._quarantine_sec > 0

    @property
    def failure_threshold(self) -> int:
        return self._failure_threshold

    @property
    def quarantine_sec(self) -> float:
        return self._quarantine_sec

    def _quarantined(self, url: str, now: float) -> bool:
        until = self._quarantine_until.get(url)
        if until is None:
            return False
        if until > now:
            return True
        # Карантин истёк — возвращаем URL в ротацию с чистого листа.
        self._quarantine_until.pop(url, None)
        return False

    def quarantined_urls(self) -> List[str]:
        now = self._clock()
        return [u for u in self._urls if self._quarantined(u, now)]

    def quarantined_now(self) -> int:
        return len(self.quarantined_urls())

    def next_url(self) -> Optional[str]:
        if not self._urls:
            return None
        now = self._clock()
        live = [u for u in self._urls if not self._quarantined(u, now)]
        if not live:
            # Все мёртвые: не блокируем трафик — пробуем тот, что выйдет из карантина раньше.
            self.quarantine_skips += 1
            return min(self._urls, key=lambda u: self._quarantine_until.get(u, 0.0))
        if len(live) < len(self._urls):
            self.quarantine_skips += 1
        if self._rotation == "random":
            return random.choice(live)
        live_set = set(live)
        n = len(self._urls)
        for step in range(1, n + 1):
            cand = self._urls[(self._idx + step) % n]
            if cand in live_set:
                self._idx = (self._idx + step) % n
                return cand
        return live[0]

    def mark_failure(self, url: Optional[str]) -> bool:
        """Учесть connect-ошибку прокси. True — если URL только что ушёл в карантин."""
        if not url or url not in self._urls:
            return False
        streak = int(self._fail_streak.get(url, 0)) + 1
        self._fail_streak[url] = streak
        if not self.health_enabled or streak < self._failure_threshold:
            return False
        self._fail_streak[url] = 0
        self._quarantine_until[url] = self._clock() + self._quarantine_sec
        self.quarantine_events += 1
        return True

    def mark_success(self, url: Optional[str]) -> None:
        if not url:
            return
        self._fail_streak.pop(url, None)
        self._quarantine_until.pop(url, None)

    def snapshot(self) -> Dict[str, int]:
        """Числовые счётчики для метрик (prometheus/лог)."""
        return {
            "proxy_urls_total": len(self._urls),
            "proxy_quarantined": self.quarantined_now(),
            "proxy_quarantine_events": self.quarantine_events,
            "proxy_quarantine_skips": self.quarantine_skips,
        }
