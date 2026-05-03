"""Контракт настроек Meilisearch в репозитории (дедуп, фильтруемые поля)."""

from __future__ import annotations

import json
from pathlib import Path


def _index_settings_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "infrastructure" / "meilisearch" / "index_settings.json"


def test_meili_index_settings_json_loads():
    path = _index_settings_path()
    assert path.is_file(), f"missing {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    filt = data.get("filterableAttributes")
    assert isinstance(filt, list)
    assert "catalog_dedupe_key" in filt
    assert data.get("distinctAttribute") == "catalog_dedupe_key"
