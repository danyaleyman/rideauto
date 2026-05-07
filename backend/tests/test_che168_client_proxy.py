"""Прокси AsyncChe168Client: sticky session / bootstrap URL."""
from __future__ import annotations

import logging

import pytest

from scraper_pipeline.che168.client import AsyncChe168Client, ensure_che168_deviceid


@pytest.fixture
def log() -> logging.Logger:
    return logging.getLogger("test_che168_client")


def test_session_proxy_url_takes_precedence(log: logging.Logger) -> None:
    config = {
        "che168": {"deviceid": "dev", "_session_proxy_url": "http://sticky:8000"},
        "proxy": {"enabled": True, "sticky_session": True, "urls": ["http://a:1", "http://b:2"]},
    }
    c = AsyncChe168Client(config, log)
    assert c.proxy_pool.all() == ["http://sticky:8000"]


def test_sticky_session_uses_only_first_url(log: logging.Logger) -> None:
    config = {
        "che168": {"deviceid": "dev"},
        "proxy": {"enabled": True, "sticky_session": True, "urls": ["http://first:1", "http://second:2"]},
    }
    c = AsyncChe168Client(config, log)
    assert c.proxy_pool.all() == ["http://first:1"]


def test_sticky_session_false_rotates_all(log: logging.Logger) -> None:
    config = {
        "che168": {"deviceid": "dev"},
        "proxy": {
            "enabled": True,
            "sticky_session": False,
            "urls": ["http://first:1", "http://second:2"],
        },
    }
    c = AsyncChe168Client(config, log)
    assert c.proxy_pool.all() == ["http://first:1", "http://second:2"]


def test_proxy_disabled_empty(log: logging.Logger) -> None:
    config = {
        "che168": {"deviceid": "dev"},
        "proxy": {"enabled": False, "urls": ["http://x:1"]},
    }
    c = AsyncChe168Client(config, log)
    assert c.proxy_pool.all() == []


def test_che168_local_proxy_config_overrides_global(log: logging.Logger) -> None:
    config = {
        "proxy": {"enabled": True, "urls": ["http://global:1"]},
        "che168": {"deviceid": "dev", "proxy": {"enabled": True, "urls": ["http://local:9"]}},
    }
    c = AsyncChe168Client(config, log)
    assert c.proxy_pool.all() == ["http://local:9"]


def test_ensure_che168_deviceid_generates_when_empty(log: logging.Logger) -> None:
    config: dict = {"che168": {"deviceid": ""}}
    d = ensure_che168_deviceid(config, log)
    assert len(d) == 36 and d.count("-") == 4
    assert config["che168"]["deviceid"] == d


def test_ensure_che168_deviceid_keeps_existing(log: logging.Logger) -> None:
    config = {"che168": {"deviceid": "  fixed-uuid  "}}
    assert ensure_che168_deviceid(config, log) == "fixed-uuid"
    assert config["che168"]["deviceid"].strip() == "fixed-uuid"


def test_async_client_fills_empty_deviceid(log: logging.Logger) -> None:
    config = {"che168": {"deviceid": ""}, "proxy": {"enabled": False}}
    c = AsyncChe168Client(config, log)
    assert c._deviceid == config["che168"]["deviceid"]
    assert len(c._deviceid) >= 32


def test_client_snapshot_metrics_has_expected_keys(log: logging.Logger) -> None:
    c = AsyncChe168Client({"che168": {"deviceid": "dev"}}, log)
    m = c.snapshot_metrics()
    assert "requests_total" in m
    assert "circuit_breaker_opened" in m
    assert "circuit_breaker_short_circuit" in m


def test_client_circuit_breaker_opens_on_streak(log: logging.Logger) -> None:
    c = AsyncChe168Client(
        {
            "che168": {
                "deviceid": "dev",
                "circuit_breaker_fail_streak": 2,
                "circuit_breaker_open_sec": 5,
                "circuit_breaker_statuses": [429],
            }
        },
        log,
    )
    c._record_failure_for_circuit_breaker(429, "rate")
    assert c._cb_open_until_mono == 0.0
    c._record_failure_for_circuit_breaker(429, "rate")
    assert c._cb_open_until_mono > 0.0
    assert c.snapshot_metrics().get("circuit_breaker_opened", 0) >= 1
