"""Unit tests for Scraper Resilience Platform (no live network)."""

from __future__ import annotations

import asyncio
import logging

import pytest

from scraper_pipeline.resilience.browser_profile import (
    list_known_impersonates,
    normalize_impersonate,
    resolve_browser_profile,
)
from scraper_pipeline.resilience.challenge import (
    ChallengeDeferredError,
    ChallengeNeedsHumanError,
    EscalationLevel,
    apply_cookie_inject_to_che168_config,
    detect_challenge,
    escalate_che168_session,
    handle_challenge_deferred,
    load_cookie_inject_file,
    max_auto_level,
    next_level_after_failure,
)
from scraper_pipeline.resilience.policy import AdaptiveConcurrencyGate, build_resilience_policy
from scraper_pipeline.resilience.prometheus import resilience_metric_lines
from scraper_pipeline.resilience.session_bundle import SessionBundle
from scraper_pipeline.resilience.transport import (
    AsyncHttpTransport,
    resolve_transport_backend,
    resolve_transport_max_clients,
    split_proxy_url,
)


def test_normalize_impersonate_aliases() -> None:
    assert normalize_impersonate("chrome") == "chrome131"
    assert normalize_impersonate("CHROME131") == "chrome131"
    assert normalize_impersonate("unknown") == "chrome131"
    assert "chrome131" in list_known_impersonates()


def test_browser_profile_coherent_ua() -> None:
    p = resolve_browser_profile({"http": {"impersonate": "chrome131"}})
    assert p.impersonate == "chrome131"
    assert "Chrome/131" in p.user_agent
    assert "131" in p.sec_ch_ua
    h = p.default_headers()
    assert h["User-Agent"] == p.user_agent


def test_split_proxy_url_with_auth() -> None:
    url, auth = split_proxy_url("http://user%40x:p%40ss@10.0.0.1:8080")
    assert url == "http://10.0.0.1:8080"
    assert auth == ("user@x", "p@ss")
    assert split_proxy_url(None) == (None, None)


def test_resolve_transport_backend() -> None:
    assert resolve_transport_backend({"http": {"transport": "curl_cffi"}}) == "curl_cffi"
    assert resolve_transport_backend({"http": {"transport": "aiohttp"}}) == "aiohttp"
    assert resolve_transport_backend({}) == "curl_cffi"


def test_resolve_transport_max_clients_beats_curl_default() -> None:
    # curl_cffi AsyncSession(max_clients=10) — потолок на всю сессию: без явного значения
    # http.concurrency > 10 не даёт прироста (2.2 vs 17.1 req/s в прод-замере 2026-10-10).
    # авто-правило: max(32, concurrency, conn_limit_per_host) * 2
    assert resolve_transport_max_clients({"http": {"concurrency": 24}}, conn_limit=24) == 64
    assert resolve_transport_max_clients({"http": {"transport_max_clients": 64}}, conn_limit=4) == 64
    assert resolve_transport_max_clients({"http": {"transport_max_clients": 0}}, conn_limit=4) == 64
    assert resolve_transport_max_clients({"http": {"transport_max_clients": "junk"}}, conn_limit=8) == 64
    assert resolve_transport_max_clients({"http": {"concurrency": 48}}, conn_limit=48) == 96
    assert resolve_transport_max_clients({}, conn_limit=10) == 64
    # даже при дефолтном conn_limit правило даёт заметно больше curl_cffi-дефолта 10
    assert resolve_transport_max_clients({}) > 10


def test_transport_passes_max_clients_to_curl_session(monkeypatch) -> None:
    curl_requests = pytest.importorskip("curl_cffi.requests", reason="curl_cffi not installed")

    captured: dict = {}

    class _FakeAsyncSession:
        def __init__(self, *args, **kwargs) -> None:
            captured.update(kwargs)

        async def close(self) -> None:
            return None

    monkeypatch.setattr(curl_requests, "AsyncSession", _FakeAsyncSession)
    cfg = {"http": {"transport": "curl_cffi", "concurrency": 24, "conn_limit_per_host": 24}}
    log = logging.getLogger("test.transport")

    async def _run() -> None:
        async with AsyncHttpTransport(cfg, log, source="encar") as transport:
            assert transport.transport_max_clients == 64
            assert transport.metrics_for_prometheus()["transport_max_clients"] == 64

    asyncio.run(_run())
    assert captured.get("max_clients") == 64


def test_session_bundle_public_dict() -> None:
    b = SessionBundle(
        source="che168",
        cookies={"sessionid": "secret", "area": "0"},
        proxy_url="http://p:1",
        impersonate_id="chrome131",
    )
    pub = b.to_public_dict()
    assert pub["has_sessionid"] is True
    assert "secret" not in str(pub)
    assert b.sessionid() == "secret"


def test_adaptive_gate_and_policy_degrade() -> None:
    async def _run() -> None:
        pol = build_resilience_policy(
            {
                "http": {"concurrency": 4},
                "resilience": {"degrade_after_block_streak": 2, "min_concurrency": 1},
                "che168": {"allow_runtime_session_refresh": True},
            },
            source="che168",
            logger=logging.getLogger("test"),
        )
        assert pol.gate is not None
        assert pol.gate.limit == 4
        pol.record_http_status(403)
        pol.record_http_status(429)
        assert pol.gate.limit == 2
        assert pol.jitter_multiplier() > 1.0
        assert pol.should_refresh_session(session_hint=True, http_status=403) is True
        pol.mark_session_refreshed()
        assert pol.should_refresh_session(session_hint=True, http_status=403) is False

        gate = AdaptiveConcurrencyGate(2)
        await gate.acquire()
        await gate.acquire()
        gate.set_limit(1)
        # third acquire would block — don't wait; just ensure release works
        await gate.release()
        await gate.release()

    asyncio.run(_run())


def test_detect_challenge_and_deferred_handler() -> None:
    sig = detect_challenge(http_status=403, body_text="<html>cf-browser-verification</html>")
    assert sig is not None
    assert sig.kind == "http_interstitial"
    pol = build_resilience_policy({"http": {"concurrency": 2}}, source="encar")
    try:
        handle_challenge_deferred(sig, pol)
        assert False, "expected ChallengeDeferredError"
    except ChallengeDeferredError:
        pass
    assert pol.snapshot_metrics()["policy_challenge_detected_total"] == 1


def test_resilience_prometheus_lines() -> None:
    lines = resilience_metric_lines(
        {
            "transport_metrics": {
                "transport_impersonate": "chrome131",
                "transport_backend": "curl_cffi",
                "transport_requests_total": 10,
                "transport_requests_ok": 9,
            },
            "policy_metrics": {
                "policy_session_age_seconds": 12.5,
                "policy_session_refresh_total": 1,
                "policy_challenge_detected_total": 0,
                "policy_degrade_events": 1,
                "policy_concurrency_limit": 3,
            },
            "session_refreshes": 1,
        },
        source="che168",
    )
    text = "\n".join(lines)
    assert 'scraper_transport_impersonateinfo{source="che168"' in text
    assert "scraper_session_refresh_total" in text
    assert "scraper_challenge_detected_total" in text
    assert "scraper_policy_concurrency_limit" in text


def test_encar_policy_session_off_by_default() -> None:
    pol = build_resilience_policy({"http": {"concurrency": 8}}, source="encar")
    assert pol.allow_session_refresh is False
    assert pol.should_refresh_session(session_hint=True, http_status=403) is False


def test_challenge_escalation_ladder_and_l3_inject(tmp_path) -> None:
    assert next_level_after_failure(EscalationLevel.L0_HTTP) == EscalationLevel.L1_SESSION_HEADLESS
    assert next_level_after_failure(EscalationLevel.L3_COOKIE_INJECT) == EscalationLevel.HUMAN
    assert max_auto_level({"resilience": {"challenge_max_level": 1}}) == EscalationLevel.L1_SESSION_HEADLESS

    log = logging.getLogger("test.challenge")
    cfg: dict = {"che168": {}}
    assert escalate_che168_session(cfg, log, level=EscalationLevel.L0_HTTP) == EscalationLevel.L0_HTTP

    cookie_path = tmp_path / "cookies.json"
    cookie_path.write_text('{"sessionid": "sid-abc", "area": "1"}', encoding="utf-8")
    loaded = load_cookie_inject_file(cookie_path)
    assert loaded["sessionid"] == "sid-abc"
    apply_cookie_inject_to_che168_config(cfg, loaded, log)
    assert cfg["che168"]["sessionid"] == "sid-abc"

    cfg2 = {
        "resilience": {
            "challenge_max_level": 3,
            "cookie_inject_path": str(cookie_path),
        },
        "che168": {},
    }
    pol = build_resilience_policy({"http": {"concurrency": 2}}, source="che168")
    got = escalate_che168_session(cfg2, log, level=EscalationLevel.L3_COOKIE_INJECT, policy=pol)
    assert got == EscalationLevel.L3_COOKIE_INJECT
    assert cfg2["che168"]["cookies"]["sessionid"] == "sid-abc"

    try:
        escalate_che168_session(
            {"resilience": {"challenge_max_level": 1}},
            log,
            level=EscalationLevel.L3_COOKIE_INJECT,
        )
        assert False, "expected ChallengeNeedsHumanError"
    except ChallengeNeedsHumanError:
        pass
