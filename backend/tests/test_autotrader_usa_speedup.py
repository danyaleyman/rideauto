"""USA Autotrader stable-speedup knobs: proxy pool, soft-cap, sticky cfg."""

from __future__ import annotations

from scraper_pipeline.autotrader.browser_ingest import _cfg_from_config
from scraper_pipeline.autotrader.session import (
    _autotrader_proxy_url_list,
    build_autotrader_proxy_pool,
)


def test_autotrader_proxy_url_list_from_env_and_yaml(monkeypatch) -> None:
    monkeypatch.setenv("AUTOTRADER_PROXY_URLS", "http://a:1@h1:80,http://b:2@h2:80")
    monkeypatch.delenv("ENCAR_PROXY_URLS", raising=False)
    monkeypatch.delenv("ENCAR_PROXY_URL", raising=False)
    cfg = {
        "autotrader": {"bootstrap_proxy_url": "http://c:3@h3:80"},
        "proxy": {"enabled": True, "urls": ["http://d:4@h4:80"]},
    }
    urls = _autotrader_proxy_url_list(cfg)
    assert urls[0] == "http://c:3@h3:80"
    assert "http://a:1@h1:80" in urls
    assert "http://d:4@h4:80" in urls


def test_autotrader_proxy_falls_back_to_encar_pool(monkeypatch) -> None:
    monkeypatch.delenv("AUTOTRADER_PROXY_URLS", raising=False)
    monkeypatch.delenv("AUTOTRADER_PROXY_URL", raising=False)
    monkeypatch.setenv(
        "ENCAR_PROXY_URLS",
        "http://e1:p@geo.example:10080,http://e2:p@geo.example:10080",
    )
    urls = _autotrader_proxy_url_list({"autotrader": {}, "proxy": {"enabled": True}})
    assert len(urls) == 2
    assert urls[0].startswith("http://e1:")


def test_build_autotrader_proxy_pool_quarantine_defaults(monkeypatch) -> None:
    monkeypatch.delenv("AUTOTRADER_PROXY_URLS", raising=False)
    monkeypatch.delenv("AUTOTRADER_PROXY_URL", raising=False)
    pool = build_autotrader_proxy_pool(
        {
            "autotrader": {},
            "proxy": {
                "urls": ["http://u:p@h:1", "http://u:p@h:2"],
                "failure_threshold": 2,
                "quarantine_sec": 60,
            },
        }
    )
    assert pool.enabled
    assert pool.failure_threshold == 2
    assert pool.quarantine_sec == 60.0
    assert pool.mark_failure("http://u:p@h:1") is False
    assert pool.mark_failure("http://u:p@h:1") is True
    assert pool.quarantined_now() == 1
    live = pool.next_url()
    assert live == "http://u:p@h:2"


def test_cfg_soft_caps_detail_concurrency() -> None:
    cfg = _cfg_from_config({"autotrader": {"detail_concurrency": 8, "require_vdp": True}})
    assert cfg.detail_conc == 3
    cfg2 = _cfg_from_config(
        {"autotrader": {"detail_concurrency": 8, "detail_concurrency_force": True}}
    )
    assert cfg2.detail_conc == 8


def test_yaml_like_prod_detail_force_four() -> None:
    cfg = _cfg_from_config(
        {
            "autotrader": {
                "detail_concurrency": 4,
                "detail_concurrency_force": True,
                "list_pause_when_pending_above": 10000,
            }
        }
    )
    assert cfg.detail_conc == 4
    assert cfg.list_pause_when_pending_above == 10000


def test_cfg_list_pause_and_sticky_defaults() -> None:
    cfg = _cfg_from_config(
        {
            "autotrader": {
                "list_pause_when_pending_above": 5000,
                "sticky_browser_slots": True,
                "http_first": True,
                "require_vdp": True,
                "detail_concurrency": 2,
            }
        }
    )
    assert cfg.list_pause_when_pending_above == 5000
    assert cfg.sticky_browser_slots is True
    assert cfg.http_first is True
    assert cfg.require_vdp is True
    assert cfg.detail_conc == 2
