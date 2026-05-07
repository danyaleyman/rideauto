from __future__ import annotations

from scraper_pipeline.che168.runtime_stats import Che168Stats


def test_runtime_stats_accumulate() -> None:
    s = Che168Stats(enabled=True)
    s.add_photos(downloaded=3, failed=1)
    s.mark_with_spec()
    snap = s.snapshot()
    assert snap["photos_downloaded"] == 3
    assert snap["photos_failed"] == 1
    assert snap["cars_with_spec"] == 1
