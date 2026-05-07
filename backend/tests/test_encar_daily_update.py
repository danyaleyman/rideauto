from __future__ import annotations

from pathlib import Path

from encar_daily_update import _chunked, _write_daily_prometheus_textfile


def test_chunked_splits_ids() -> None:
    ids = ["1", "2", "3", "4", "5"]
    chunks = list(_chunked(ids, 2))
    assert chunks == [["1", "2"], ["3", "4"], ["5"]]


def test_write_daily_prometheus_textfile(tmp_path: Path) -> None:
    p = tmp_path / "encar_daily.prom"
    stats = {"new_cars_added": 11, "sold_cars_removed": 3, "pending_queue_size": 25}

    class _Log:
        def debug(self, *_a, **_k):
            return None

    _write_daily_prometheus_textfile(str(p), stats, _Log())
    text = p.read_text(encoding="utf-8")
    assert "encar_daily_new_cars 11" in text
    assert "encar_daily_sold_cars 3" in text
    assert "encar_daily_pending 25" in text
