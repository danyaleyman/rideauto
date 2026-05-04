import pytest

from scraper_pipeline.che168.taxonomy_sync import (
    discover_che168_series_api_path,
    merge_series_for_brand_into_taxonomy,
)


def test_merge_series_builds_seriesid_map():
    tax: dict = {"model_aliases": {}}
    payload = {
        "result": {
            "list": [
                {"seriesid": 101, "seriesname": "3系"},
                {"seriesid": 102, "name": "5系"},
            ]
        }
    }
    n = merge_series_for_brand_into_taxonomy(tax, 15, payload)
    assert n == 2
    assert tax["seriesid_to_model_name"]["101"] == "3系"
    assert tax["seriesid_to_model_name"]["102"] == "5系"
    assert tax["series_by_brandid"]["15"][0]["seriesid"] == 101
    assert "che168_series_api" in tax["taxonomy_source"]


class _Log:
    def info(self, *a, **k) -> None:
        pass

    def warning(self, *a, **k) -> None:
        pass


class _Client:
    def __init__(self, good_path: str) -> None:
        self._good = good_path

    async def _request(self, method, path, params=None):
        if str(path).strip() == self._good:
            return (
                {
                    "returncode": 0,
                    "result": {"list": [{"seriesid": 1, "name": "A"}]},
                },
                200,
                None,
            )
        return ({}, 404, "nope")


@pytest.mark.asyncio
async def test_discover_series_api_path_picks_first_working():
    log = _Log()
    config = {
        "che168": {
            "series_api_path": "",
            "series_api_path_candidates": ["bad", "series", "worse"],
            "taxonomy": {"brand_by_id": {"9": "X", "1": "Y"}},
        }
    }
    client = _Client("series")
    ok = await discover_che168_series_api_path(client, config, log)
    assert ok is True
    assert config["che168"]["series_api_path"] == "series"
