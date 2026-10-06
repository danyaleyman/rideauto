"""Facet denylist YAML drops junk values from public distributions."""

from __future__ import annotations

from fastapi_app.facet_normalize import _is_facet_junk_value, _load_facet_denylist


def test_facet_denylist_yaml_loaded() -> None:
    cfg = _load_facet_denylist()
    assert isinstance(cfg, dict)
    assert "global" in cfg
    assert "null" in {str(x).lower() for x in (cfg.get("global") or [])}


def test_facet_junk_global_and_by_attr() -> None:
    assert _is_facet_junk_value("null") is True
    assert _is_facet_junk_value("N/A") is True
    assert _is_facet_junk_value("0", "transmission") is True
    assert _is_facet_junk_value("Автомат", "transmission") is False
