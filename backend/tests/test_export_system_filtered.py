"""Регрессия: export_filtered_data → JSON с полем filters (раньше был NameError)."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from export_system import ExportSystem


class _MockDb:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows
        self.last_filters: Dict[str, Any] | None = None

    def get_cars_by_filters(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        self.last_filters = dict(filters)
        return list(self._rows)


def test_export_filtered_json_contains_filters_and_cars(tmp_path):
    rows = [
        {
            "id": 1,
            "inner_id": "enc-x",
            "mark": "Kia",
            "model": "Rio",
            "year": "2021",
        }
    ]
    out = tmp_path / "filtered.json"
    db = _MockDb(rows)
    exporter = ExportSystem(db)
    path = exporter.export_filtered_data({"mark": "Kia"}, "json", str(out))

    assert path == str(out)
    assert db.last_filters == {"mark": "Kia"}

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["filters"] == {"mark": "Kia"}
    assert data["total_cars"] == 1
    assert len(data["cars"]) == 1
    assert data["cars"][0].get("mark") == "Kia"
    assert data["cars"][0].get("model") == "Rio"


def test_export_filtered_empty_cars_still_writes_filters(tmp_path):
    out = tmp_path / "empty.json"
    db = _MockDb([])
    exporter = ExportSystem(db)
    exporter.export_filtered_data({"model": "NoneSuch"}, "json", str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["filters"] == {"model": "NoneSuch"}
    assert data["total_cars"] == 0
    assert data["cars"] == []
