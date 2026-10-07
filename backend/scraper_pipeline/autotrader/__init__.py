"""Autotrader USA pipeline package."""

from scraper_pipeline.autotrader.parser import (
    car_id_for_listing,
    normalize_listing,
    parse_srp_page,
    parse_vdp_page,
)

__all__ = [
    "AsyncAutotraderClient",
    "car_id_for_listing",
    "normalize_listing",
    "parse_srp_page",
    "parse_vdp_page",
    "run_autotrader_ingest",
]


def __getattr__(name: str):
    if name == "AsyncAutotraderClient":
        from scraper_pipeline.autotrader.client import AsyncAutotraderClient

        return AsyncAutotraderClient
    if name == "run_autotrader_ingest":
        from scraper_pipeline.autotrader.workers import run_autotrader_ingest

        return run_autotrader_ingest
    raise AttributeError(name)
