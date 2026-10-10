from __future__ import annotations

from scraper_pipeline.common.backoff import build_backoff_config
from scraper_pipeline.common.proxy_pool import ProxyPool


class _Clock:
    """Управляемые monotonic-часы для тестов карантина."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _pool(
    *,
    urls: list[str] | None = None,
    failure_threshold: int = 2,
    quarantine_sec: float = 60.0,
    rotation: str = "round_robin",
    clock: _Clock | None = None,
):
    from scraper_pipeline.common.proxy_pool import ProxyPool

    return ProxyPool(
        urls if urls is not None else ["http://a:1", "http://b:2", "http://c:3"],
        rotation=rotation,
        failure_threshold=failure_threshold,
        quarantine_sec=quarantine_sec,
        clock=clock or _Clock(),
    )


def test_proxy_pool_round_robin_still_works_without_health() -> None:
    p = _pool(failure_threshold=0, quarantine_sec=0.0)
    assert [p.next_url() for _ in range(4)] == ["http://a:1", "http://b:2", "http://c:3", "http://a:1"]


def test_proxy_pool_quarantine_needs_threshold_and_skips_dead_url() -> None:
    clk = _Clock()
    p = _pool(failure_threshold=2, quarantine_sec=60.0, clock=clk)
    assert p.mark_failure("http://a:1") is False  # 1-я ошибка — только серия
    assert p.quarantined_now() == 0
    assert p.mark_failure("http://a:1") is True  # 2-я подряд — карантин
    assert p.quarantined_now() == 1
    assert p.quarantine_events == 1

    picked = {p.next_url() for _ in range(6)}
    assert picked == {"http://b:2", "http://c:3"}
    assert p.quarantine_skips >= 1


def test_proxy_pool_quarantine_expires_after_cooldown() -> None:
    clk = _Clock()
    p = _pool(urls=["http://a:1", "http://b:2"], failure_threshold=1, quarantine_sec=30.0, clock=clk)
    assert p.mark_failure("http://a:1") is True
    assert {p.next_url() for _ in range(4)} == {"http://b:2"}
    clk.t += 30.0
    assert p.quarantined_now() == 0
    assert "http://a:1" in {p.next_url() for _ in range(4)}


def test_proxy_pool_all_quarantined_never_returns_none() -> None:
    clk = _Clock()
    p = _pool(urls=["http://a:1", "http://b:2"], failure_threshold=1, quarantine_sec=30.0, clock=clk)
    p.mark_failure("http://a:1")
    clk.t = 1.0
    p.mark_failure("http://b:2")
    assert p.quarantined_now() == 2
    urls = [p.next_url() for _ in range(4)]
    assert all(u in {"http://a:1", "http://b:2"} for u in urls)
    assert p.quarantine_skips == 4


def test_proxy_pool_success_resets_streak_and_clears_quarantine() -> None:
    p = _pool(failure_threshold=2, quarantine_sec=60.0)
    assert p.mark_failure("http://a:1") is False
    p.mark_success("http://a:1")  # успешный ответ обнуляет серию
    assert p.mark_failure("http://a:1") is False
    assert p.quarantined_now() == 0

    assert p.mark_failure("http://a:1") is True  # 2 подряд → карантин
    p.mark_success("http://a:1")  # прокси ожил — снимаем карантин
    assert p.quarantined_now() == 0


def test_proxy_pool_random_rotation_respects_quarantine() -> None:
    clk = _Clock()
    p = _pool(
        urls=["http://a:1", "http://b:2", "http://c:3"],
        failure_threshold=1,
        quarantine_sec=60.0,
        rotation="random",
        clock=clk,
    )
    p.mark_failure("http://b:2")
    p.mark_failure("http://c:3")
    assert {p.next_url() for _ in range(8)} == {"http://a:1"}


def test_proxy_pool_snapshot_exposes_counters() -> None:
    p = _pool(failure_threshold=1, quarantine_sec=60.0)
    p.mark_failure("http://a:1")
    snap = p.snapshot()
    assert snap["proxy_urls_total"] == 3
    assert snap["proxy_quarantined"] == 1
    assert snap["proxy_quarantine_events"] == 1
    assert isinstance(snap["proxy_quarantine_skips"], int)


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
