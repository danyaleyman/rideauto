from __future__ import annotations

import asyncio

from scraper_pipeline.che168.workers import build_segments, detect_search_pagination_mode


def test_build_segments_price_x_year_count_and_keys() -> None:
    seg_cfg = {
        "enabled": True,
        "strategy": "price_x_year",
        "price_segments": [[0, 5000], [5000, 10000], [100000, 0]],
        "year_segments": [[2020, 2021], [2022, 2023]],
        "max_segments_per_brand": 100,
    }
    segments = build_segments(seg_cfg)
    assert len(segments) == 6
    assert segments[0]["key"] == "price_0_5000_year_2020_2021"
    assert segments[1]["key"] == "price_0_5000_year_2022_2023"
    assert segments[-1]["key"] == "price_100000_plus_year_2022_2023"
    assert segments[-1]["price_max"] is None


def test_build_segments_respects_max_segments_per_brand() -> None:
    seg_cfg = {
        "enabled": True,
        "strategy": "price_x_year",
        "price_segments": [[0, 5000], [5000, 10000], [10000, 15000]],
        "year_segments": [[2020, 2021], [2022, 2023], [2024, 2025]],
        "max_segments_per_brand": 4,
    }
    segments = build_segments(seg_cfg)
    assert len(segments) == 4


def test_build_segments_disabled_returns_default_segment() -> None:
    assert build_segments({"enabled": False}) == [{}]


class _FakeClientOffsetSupported:
    async def fetch_search_with_offset(self, **kwargs):
        offset = int(kwargs.get("offset", 0))
        if offset == 0:
            return (
                {
                    "returncode": 0,
                    "result": {"list": [{"id": "1001"}, {"id": "1002"}]},
                },
                200,
                None,
            )
        return (
            {
                "returncode": 0,
                "result": {"list": [{"id": "2001"}, {"id": "2002"}]},
            },
            200,
            None,
        )


class _FakeClientOffsetNotSupported:
    async def fetch_search_with_offset(self, **kwargs):
        return None, 404, "not supported"


class _NoopLog:
    def info(self, *args, **kwargs):
        return None


def test_detect_pagination_mode_auto_selects_offset() -> None:
    mode = asyncio.run(
        detect_search_pagination_mode(
            _FakeClientOffsetSupported(),
            preferred_mode="auto",
            probe_brandid=575,
            pagesize=20,
            sort=0,
            vehicle_list=0,
            probe_segment={"price_min": 0, "price_max": 5000},
            log=_NoopLog(),
        )
    )
    assert mode == "offset"


def test_detect_pagination_mode_auto_falls_back_to_pageindex() -> None:
    mode = asyncio.run(
        detect_search_pagination_mode(
            _FakeClientOffsetNotSupported(),
            preferred_mode="auto",
            probe_brandid=575,
            pagesize=20,
            sort=0,
            vehicle_list=0,
            probe_segment={},
            log=_NoopLog(),
        )
    )
    assert mode == "pageindex"


def test_detect_pagination_mode_respects_explicit_mode() -> None:
    mode = asyncio.run(
        detect_search_pagination_mode(
            _FakeClientOffsetNotSupported(),
            preferred_mode="offset",
            probe_brandid=575,
            pagesize=20,
            sort=0,
            vehicle_list=0,
            probe_segment={},
            log=_NoopLog(),
        )
    )
    assert mode == "offset"
