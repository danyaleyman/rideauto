from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load():
    import sys

    root = Path(__file__).resolve().parents[2]
    p = root / "infrastructure" / "meilisearch" / "sync_meilisearch.py"
    name = "sync_meilisearch"
    spec = importlib.util.spec_from_file_location(name, str(p))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _FakeApiError(Exception):
    pass


def test_wait_for_task_resilient_retries_408_then_succeeds(monkeypatch):
    mod = _load()
    # Patch the name used inside the module.
    monkeypatch.setattr(mod, "MeilisearchApiError", _FakeApiError)
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)

    calls = {"n": 0}

    class Client:
        def wait_for_task(self, uid, timeout_in_ms=0):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _FakeApiError("MeilisearchApiError. 408 Client Error: Request Timeout")
            return SimpleNamespace(status="succeeded", uid=uid)

        def get_task(self, uid):
            raise _FakeApiError("still flaky")

    out = mod.wait_for_task_resilient(Client(), 42, retries=5)
    assert out.status == "succeeded"
    assert calls["n"] == 3


def test_wait_for_task_resilient_uses_get_task_if_already_done(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "MeilisearchApiError", _FakeApiError)
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)

    class Client:
        def wait_for_task(self, uid, timeout_in_ms=0):
            raise _FakeApiError("408 Request Timeout")

        def get_task(self, uid):
            return SimpleNamespace(status="succeeded", uid=uid)

    out = mod.wait_for_task_resilient(Client(), 7, retries=3)
    assert out.status == "succeeded"


def test_wait_for_task_resilient_rethrows_non_timeout(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "MeilisearchApiError", _FakeApiError)

    class Client:
        def wait_for_task(self, uid, timeout_in_ms=0):
            raise _FakeApiError("invalid_api_key")

        def get_task(self, uid):
            raise AssertionError("should not poll")

    with pytest.raises(_FakeApiError, match="invalid_api_key"):
        mod.wait_for_task_resilient(Client(), 1, retries=3)
