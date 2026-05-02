from __future__ import annotations

import json
from pathlib import Path

from catalog_model_cluster import compute_model_cluster, load_model_cluster_rules


def test_load_rules_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "rules.json"
    empty.write_text("{}", encoding="utf-8")
    load_model_cluster_rules.cache_clear()
    assert isinstance(load_model_cluster_rules(str(empty)), dict)


def test_heuristic_strips_tail_hybrid(tmp_path: Path) -> None:
    p = tmp_path / "rules.json"
    p.write_text("{}", encoding="utf-8")
    assert compute_model_cluster("Hyundai", "Santa Fe Hybrid", rules_path=str(p)) == "Santa Fe"


def test_explicit_by_brand(tmp_path: Path) -> None:
    p = tmp_path / "rules.json"
    p.write_text(
        json.dumps({"by_brand": {"kia": {"Ceed Sportswagon": "Ceed"}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    assert compute_model_cluster("Kia", "Ceed Sportswagon", rules_path=str(p)) == "Ceed"


def test_fallback_same_when_no_strip(tmp_path: Path) -> None:
    p = tmp_path / "rules.json"
    p.write_text("{}", encoding="utf-8")
    assert compute_model_cluster("BMW", "X5", rules_path=str(p)) == "X5"
