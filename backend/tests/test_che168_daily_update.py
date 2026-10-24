from __future__ import annotations

from pathlib import Path

from che168_daily_update import (
    _chunked,
    _external_infoid_from_car_id,
    _select_brand_window,
    _write_daily_prometheus_textfile,
)


def test_select_brand_window_all_brands_when_no_limit() -> None:
    ids = [1, 2, 3, 4]
    assert _select_brand_window(ids, 0, 0) == (ids, 0)
    assert _select_brand_window(ids, 10, 3) == (ids, 0)


def test_select_brand_window_rotates() -> None:
    ids = list(range(1, 11))
    first, cursor = _select_brand_window(ids, 4, 0)
    assert first == [1, 2, 3, 4]
    assert cursor == 4
    second, cursor2 = _select_brand_window(ids, 4, cursor)
    assert second == [5, 6, 7, 8]
    third, cursor3 = _select_brand_window(ids, 4, cursor2)
    assert third == [9, 10, 1, 2]  # окно заворачивается по кругу
    assert cursor3 == 2


def test_select_brand_window_empty() -> None:
    assert _select_brand_window([], 5, 0) == ([], 0)


def test_external_infoid_from_car_id() -> None:
    assert _external_infoid_from_car_id("che168-12345") == "12345"
    assert _external_infoid_from_car_id(" 12345 ") == "12345"


def test_chunked_splits_ids() -> None:
    ids = ["a", "b", "c", "d", "e"]
    assert list(_chunked(ids, 2)) == [["a", "b"], ["c", "d"], ["e"]]


def test_write_daily_prometheus_textfile(tmp_path: Path) -> None:
    p = tmp_path / "che168_daily.prom"
    stats = {"new_cars_added": 7, "sold_cars_removed": 2, "pending_queue_size": 31}

    class _Log:
        def debug(self, *_a, **_k):
            return None

    _write_daily_prometheus_textfile(str(p), stats, _Log())
    text = p.read_text(encoding="utf-8")
    assert "che168_daily_new_cars 7" in text
    assert "che168_daily_sold_cars 2" in text
    assert "che168_daily_pending 31" in text
