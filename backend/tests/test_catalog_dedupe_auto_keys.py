"""High-confidence auto-apply keys: vin: and source: (not bare id:)."""

from __future__ import annotations


def test_auto_apply_key_prefixes() -> None:
    def _auto_key(k: str) -> bool:
        return k.startswith("vin:") or k.startswith("source:")

    assert _auto_key("vin:ABC123") is True
    assert _auto_key("source:che168:999") is True
    assert _auto_key("id:encar:1") is False
    assert _auto_key("fuzzy:x") is False
