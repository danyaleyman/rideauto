from __future__ import annotations

import logging

import pytest

from scraper_pipeline.che168.image_downloader import AsyncImageDownloader


@pytest.mark.asyncio
async def test_image_downloader_disabled_returns_empty() -> None:
    dl = AsyncImageDownloader({"che168": {"image_download": {"enabled": False}}}, logging.getLogger("t"))
    out = await dl.download_many(car_id="che168-1", urls=["https://example.com/a.jpg"])
    assert out["enabled"] is False
    assert out["downloaded"] == 0
    assert out["assets"] == []


@pytest.mark.asyncio
async def test_image_downloader_enabled_empty_urls() -> None:
    dl = AsyncImageDownloader({"che168": {"image_download": {"enabled": True}}}, logging.getLogger("t"))
    out = await dl.download_many(car_id="che168-1", urls=[])
    assert out["enabled"] is True
    assert out["attempted"] == 0
    assert out["downloaded"] == 0
