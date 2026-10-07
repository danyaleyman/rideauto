"""Runtime counters for Autotrader scraper."""

from __future__ import annotations

from dataclasses import dataclass, field


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

    def as_dict(self) -> dict:
        return {
            "list_pages_ok": self.list_pages_ok,
            "list_pages_fail": self.list_pages_fail,
            "listings_seen": self.listings_seen,
            "details_ok": self.details_ok,
            "details_fail": self.details_fail,
            "saved": self.saved,
            "skipped": self.skipped,
            "errors": list(self.errors[-20:]),
        }
