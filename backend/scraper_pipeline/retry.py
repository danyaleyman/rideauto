"""Асинхронный retry с экспоненциальным backoff и опциональным jitter."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class BackoffConfig:
    base_sec: float = 1.0
    max_sec: float = 60.0
    jitter_min: float = 0.0
    jitter_max: float = 0.0

    def delay_seconds(self, attempt_zero_based: int, retry_after_header: Optional[str] = None) -> float:
        if retry_after_header and str(retry_after_header).strip().isdigit():
            return min(float(str(retry_after_header).strip()), self.max_sec)
        sec = min(self.base_sec * (2**attempt_zero_based), self.max_sec)
        if self.jitter_max > 0:
            sec += random.uniform(self.jitter_min, self.jitter_max)
        return float(sec)


async def sleep_backoff(cfg: BackoffConfig, attempt: int, retry_after: Optional[str] = None) -> None:
    delay = cfg.delay_seconds(attempt, retry_after)
    if delay > 0:
        await asyncio.sleep(delay)


async def async_retry(
    op: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    backoff: BackoffConfig,
    retry_on: Optional[Callable[[BaseException], bool]] = None,
) -> T:
    last: Optional[BaseException] = None
    for attempt in range(max_attempts):
        try:
            return await op()
        except BaseException as exc:  # noqa: BLE001
            last = exc
            if attempt + 1 >= max_attempts:
                raise
            if retry_on is not None and not retry_on(exc):
                raise
            await sleep_backoff(backoff, attempt)
    assert last is not None
    raise last
