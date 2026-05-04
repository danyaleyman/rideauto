"""Прокси AsyncChe168Client: sticky session / bootstrap URL."""
from __future__ import annotations

import logging

import pytest

from scraper_pipeline.che168.client import AsyncChe168Client


@pytest.fixture
def log() -> logging.Logger:
    return logging.getLogger("test_che168_client")


def test_session_proxy_url_takes_precedence(log: logging.Logger) -> None:
    config = {
        "che168": {"deviceid": "dev", "_session_proxy_url": "http://sticky:8000"},
        "proxy": {"enabled": True, "sticky_session": True, "urls": ["http://a:1", "http://b:2"]},
    }
    c = AsyncChe168Client(config, log)
    assert c.proxies == ["http://sticky:8000"]


def test_sticky_session_uses_only_first_url(log: logging.Logger) -> None:
    config = {
        "che168": {"deviceid": "dev"},
        "proxy": {"enabled": True, "sticky_session": True, "urls": ["http://first:1", "http://second:2"]},
    }
    c = AsyncChe168Client(config, log)
    assert c.proxies == ["http://first:1"]


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
    assert c.proxies == ["http://first:1", "http://second:2"]


def test_proxy_disabled_empty(log: logging.Logger) -> None:
    config = {
        "che168": {"deviceid": "dev"},
        "proxy": {"enabled": False, "urls": ["http://x:1"]},
    }
    c = AsyncChe168Client(config, log)
    assert c.proxies == []
