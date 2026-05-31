"""Тесты графа зависимостей autorepair (без docker/сети)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AR_DIR = _REPO_ROOT / "deploy" / "autorepair"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _AR_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


chain = _load("rideauto_autorepair_chain", "chain.py")


def test_find_root_cause_postgres_only() -> None:
    roots = chain.find_root_cause({"postgres", "api", "web"})
    assert roots == ["postgres"]


def test_find_root_cause_api_without_deps() -> None:
    roots = chain.find_root_cause({"api"})
    assert roots == ["api"]


def test_find_root_cause_meili_stale_only_api_meta() -> None:
    roots = chain.find_root_cause({"api"})
    assert roots[0] == "api"


def test_topo_includes_edge() -> None:
    ids = [c.id for c in chain.topo_order()]
    assert ids == ["postgres", "redis", "meilisearch", "api", "web", "edge"]
