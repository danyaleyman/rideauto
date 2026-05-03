"""Вспомогательные спаны OpenTelemetry для горячих путей каталога (опционально)."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


@contextmanager
def span_sync(name: str):
    try:
        from opentelemetry import trace

        with trace.get_tracer("rideauto.catalog").start_as_current_span(name):
            yield
    except Exception:
        yield


async def run_in_thread_traced(name: str, fn: Callable[[], T]) -> T:
    """asyncio.to_thread внутри спана (Meilisearch SDK — синхронный)."""
    try:
        from opentelemetry import trace

        with trace.get_tracer("rideauto.catalog").start_as_current_span(name):
            return await asyncio.to_thread(fn)
    except Exception:
        return await asyncio.to_thread(fn)


async def await_traced(name: str, coro: Awaitable[T]) -> T:
    try:
        from opentelemetry import trace

        with trace.get_tracer("rideauto.catalog").start_as_current_span(name):
            return await coro
    except Exception:
        return await coro
