"""RideAuto Scraper Resilience Platform: TLS transport, session provider, adaptive policy."""

from __future__ import annotations

from scraper_pipeline.resilience.browser_profile import BrowserProfile, resolve_browser_profile
from scraper_pipeline.resilience.policy import (
    AdaptiveConcurrencyGate,
    ResiliencePolicy,
    build_resilience_policy,
)
from scraper_pipeline.resilience.session_bundle import SessionBundle
from scraper_pipeline.resilience.transport import AsyncHttpTransport, TransportResponse

__all__ = [
    "AdaptiveConcurrencyGate",
    "AsyncHttpTransport",
    "BrowserProfile",
    "ResiliencePolicy",
    "SessionBundle",
    "TransportResponse",
    "build_resilience_policy",
    "resolve_browser_profile",
]
