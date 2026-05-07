from __future__ import annotations

from scraper_pipeline.common.backoff import build_backoff_config
from scraper_pipeline.common.proxy_pool import ProxyPool


def test_proxy_pool_round_robin() -> None:
    p = ProxyPool(["http://a:1", "http://b:2"], rotation="round_robin")
    assert p.next_url() == "http://a:1"
    assert p.next_url() == "http://b:2"
    assert p.next_url() == "http://a:1"


def test_proxy_pool_random_returns_known() -> None:
    p = ProxyPool(["http://a:1", "http://b:2"], rotation="random")
    assert p.next_url() in {"http://a:1", "http://b:2"}


def test_build_backoff_config_local_overrides_global() -> None:
    cfg = build_backoff_config(
        {"backoff_base": 1, "backoff_max": 60, "jitter": False},
        {"backoff_base": 2, "backoff_max": 30, "jitter": True, "jitter_max": 0.7},
    )
    assert cfg.base_sec == 2
    assert cfg.max_sec == 30
    assert cfg.jitter_max == 0.7
