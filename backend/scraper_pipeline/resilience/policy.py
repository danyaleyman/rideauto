"""ResiliencePolicy: эскалация сессии + adaptive concurrency."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


class AdaptiveConcurrencyGate:
    """Сжимаемый лимит параллелизма без пересоздания worker-задач."""

    def __init__(self, initial: int):
        self._limit = max(1, int(initial))
        self._in_flight = 0
        self._cond = asyncio.Condition()

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def set_limit(self, n: int) -> None:
        self._limit = max(1, int(n))

    async def acquire(self) -> None:
        async with self._cond:
            while self._in_flight >= self._limit:
                await self._cond.wait()
            self._in_flight += 1

    async def release(self) -> None:
        async with self._cond:
            self._in_flight = max(0, self._in_flight - 1)
            self._cond.notify_all()


@dataclass
class ResiliencePolicy:
    """
    Политика устойчивости:
    - при всплеске 403/429 снижает concurrency_gate
    - сигнализирует escalate_session
    - увеличивает jitter multiplier
    """

    source: str
    initial_concurrency: int = 8
    gate: Optional[AdaptiveConcurrencyGate] = None
    log: Optional[logging.Logger] = None
    degrade_after_block_streak: int = 8
    recover_after_ok_streak: int = 40
    min_concurrency: int = 1
    session_refresh_min_interval_sec: float = 90.0
    allow_session_refresh: bool = True
    _block_streak: int = 0
    _ok_streak: int = 0
    _last_session_refresh_mono: float = 0.0
    _jitter_multiplier: float = 1.0
    _metrics: Dict[str, int] = field(default_factory=dict)
    _session_age_anchor: float = 0.0

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = AdaptiveConcurrencyGate(self.initial_concurrency)
        self._metrics = {
            "policy_degrade_events": 0,
            "policy_recover_events": 0,
            "policy_session_escalate_signals": 0,
            "policy_session_refresh_total": 0,
            "policy_challenge_detected_total": 0,
            "policy_block_status_total": 0,
        }

    def snapshot_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics,
            "policy_concurrency_limit": int(self.gate.limit if self.gate else self.initial_concurrency),
            "policy_jitter_multiplier": float(self._jitter_multiplier),
            "policy_session_age_seconds": self.session_age_seconds(),
        }

    def session_age_seconds(self) -> float:
        if self._session_age_anchor <= 0:
            return 0.0
        return max(0.0, time.time() - self._session_age_anchor)

    def mark_session_refreshed(self) -> None:
        self._last_session_refresh_mono = time.monotonic()
        self._session_age_anchor = time.time()
        self._metrics["policy_session_refresh_total"] = (
            int(self._metrics.get("policy_session_refresh_total", 0) or 0) + 1
        )
        self._block_streak = 0

    def note_challenge_detected(self) -> None:
        self._metrics["policy_challenge_detected_total"] = (
            int(self._metrics.get("policy_challenge_detected_total", 0) or 0) + 1
        )

    def jitter_multiplier(self) -> float:
        return float(self._jitter_multiplier)

    def record_http_status(self, status: int, *, session_hint: bool = False) -> None:
        st = int(status or 0)
        if st in (403, 429, 407) or session_hint:
            self._block_streak += 1
            self._ok_streak = 0
            self._metrics["policy_block_status_total"] = (
                int(self._metrics.get("policy_block_status_total", 0) or 0) + 1
            )
            if self._block_streak >= max(1, self.degrade_after_block_streak):
                self._degrade()
                self._block_streak = 0
        elif 200 <= st < 300:
            self._ok_streak += 1
            self._block_streak = 0
            if self._ok_streak >= max(1, self.recover_after_ok_streak):
                self._recover()
                self._ok_streak = 0

    def _degrade(self) -> None:
        if not self.gate:
            return
        cur = self.gate.limit
        nxt = max(self.min_concurrency, cur // 2 if cur > 1 else cur)
        if nxt < cur:
            self.gate.set_limit(nxt)
            self._jitter_multiplier = min(4.0, self._jitter_multiplier * 1.5)
            self._metrics["policy_degrade_events"] = (
                int(self._metrics.get("policy_degrade_events", 0) or 0) + 1
            )
            if self.log:
                self.log.warning(
                    "ResiliencePolicy[%s]: degrade concurrency %s → %s (jitter×%.2f)",
                    self.source,
                    cur,
                    nxt,
                    self._jitter_multiplier,
                )

    def _recover(self) -> None:
        if not self.gate:
            return
        cur = self.gate.limit
        nxt = min(self.initial_concurrency, cur + 1)
        if nxt > cur or self._jitter_multiplier > 1.0:
            self.gate.set_limit(nxt)
            self._jitter_multiplier = max(1.0, self._jitter_multiplier * 0.85)
            if self._jitter_multiplier < 1.05:
                self._jitter_multiplier = 1.0
            self._metrics["policy_recover_events"] = (
                int(self._metrics.get("policy_recover_events", 0) or 0) + 1
            )
            if self.log:
                self.log.info(
                    "ResiliencePolicy[%s]: recover concurrency %s → %s (jitter×%.2f)",
                    self.source,
                    cur,
                    nxt,
                    self._jitter_multiplier,
                )

    def should_refresh_session(self, *, session_hint: bool, http_status: int = 0) -> bool:
        if not self.allow_session_refresh:
            return False
        if not session_hint and int(http_status or 0) not in (401, 403):
            return False
        now = time.monotonic()
        if now - self._last_session_refresh_mono < self.session_refresh_min_interval_sec:
            return False
        self._metrics["policy_session_escalate_signals"] = (
            int(self._metrics.get("policy_session_escalate_signals", 0) or 0) + 1
        )
        return True

    async def acquire(self) -> None:
        if self.gate:
            await self.gate.acquire()

    async def release(self) -> None:
        if self.gate:
            await self.gate.release()


def build_resilience_policy(
    config: Mapping[str, Any],
    *,
    source: str,
    logger: Optional[logging.Logger] = None,
) -> ResiliencePolicy:
    http = config.get("http") if isinstance(config.get("http"), dict) else {}
    res = config.get("resilience") if isinstance(config.get("resilience"), dict) else {}
    src_block = config.get(source) if isinstance(config.get(source), dict) else {}

    concurrency = int(http.get("concurrency", 8) or 8)
    min_c = int(res.get("min_concurrency", 1) or 1)
    degrade_after = int(res.get("degrade_after_block_streak", 8) or 8)
    recover_after = int(res.get("recover_after_ok_streak", 40) or 40)

    allow = True
    if source == "che168":
        allow = src_block.get("allow_runtime_session_refresh", True) is not False
        min_iv = float(src_block.get("session_refresh_min_interval_sec", 90) or 90)
    else:
        # Encar: session provider off by default
        allow = bool(res.get("allow_session_refresh", False) or src_block.get("allow_session_refresh", False))
        min_iv = float(res.get("session_refresh_min_interval_sec", 90) or 90)

    return ResiliencePolicy(
        source=source,
        initial_concurrency=concurrency,
        gate=AdaptiveConcurrencyGate(concurrency),
        log=logger,
        degrade_after_block_streak=degrade_after,
        recover_after_ok_streak=recover_after,
        min_concurrency=max(1, min_c),
        session_refresh_min_interval_sec=min_iv,
        allow_session_refresh=allow,
    )
