"""Runtime counters for Autotrader scraper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class AutotraderStats:
    list_pages_ok: int = 0
    list_pages_fail: int = 0
    listings_seen: int = 0
    details_ok: int = 0
    details_fail: int = 0
    saved: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    # Двухфазный контур (discovery → pending → detail)
    ids_queued: int = 0
    pending_left: int = 0
    requeued: int = 0
    gave_up: int = 0
    gone: int = 0  # снято с продажи (unavailable) — ретраить бессмысленно
    stub_saved: int = 0  # сохранён SRP-стаб после исчерпания попыток VDP
    srp_via_http: int = 0
    srp_via_browser: int = 0
    vdp_via_http: int = 0
    vdp_via_browser: int = 0
    http_disabled_after: int = 0
    extract_paths: Dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "list_pages_ok": self.list_pages_ok,
            "list_pages_fail": self.list_pages_fail,
            "listings_seen": self.listings_seen,
            "details_ok": self.details_ok,
            "details_fail": self.details_fail,
            "saved": self.saved,
            "skipped": self.skipped,
            "ids_queued": self.ids_queued,
            "pending_left": self.pending_left,
            "requeued": self.requeued,
            "gave_up": self.gave_up,
            "gone": self.gone,
            "stub_saved": self.stub_saved,
            "srp_via_http": self.srp_via_http,
            "srp_via_browser": self.srp_via_browser,
            "vdp_via_http": self.vdp_via_http,
            "vdp_via_browser": self.vdp_via_browser,
            "http_disabled_after": self.http_disabled_after,
            "extract_paths": dict(self.extract_paths),
            "errors": list(self.errors[-20:]),
        }
