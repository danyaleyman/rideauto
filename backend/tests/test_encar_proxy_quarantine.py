from __future__ import annotations

import logging
from typing import Any, Dict, List

from scraper_pipeline.encar.client import AsyncEncarClient
from scraper_pipeline.resilience.transport import TransportResponse


def _log() -> logging.Logger:
    return logging.getLogger("test_encar_proxy_quarantine")


class _FakeTransport:
    """Транспорт-заглушка: отдаёт заданные ответы по индексу вызова (последний — повторно)."""

    backend = "curl_cffi"

    def __init__(self, responses: List[TransportResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.proxies: List[Any] = []

    async def request(self, *args: Any, **kwargs: Any) -> TransportResponse:
        self.calls += 1
        self.proxies.append(kwargs.get("proxy"))
        idx = min(self.calls - 1, len(self._responses) - 1)
        return self._responses[idx]

    def metrics_for_prometheus(self) -> Dict[str, Any]:
        return {"transport_requests_total": self.calls}


def _config(*, urls: List[str], **proxy_over: Any) -> Dict[str, Any]:
    proxy: Dict[str, Any] = {"enabled": True, "urls": list(urls), "rotation": "round_robin"}
    proxy.update(proxy_over)
    return {
        "http": {"request_jitter_min": 0, "request_jitter_max": 0, "timeout_connect": 1},
        "retry": {
            "max_attempts": 1,
            "backoff_base": 0,
            "backoff_max": 0,
            "jitter": False,
            "circuit_breaker_fail_streak": 99,
            "circuit_breaker_open_sec": 1,
        },
        "proxy": proxy,
    }


def _client(cfg: Dict[str, Any], transport: _FakeTransport) -> AsyncEncarClient:
    client = AsyncEncarClient(cfg, _log())
    client._transport = transport  # noqa: SLF001 — подменяем сеть, проверяем логику карантина
    return client


_TIMEOUT = TransportResponse(status=0, error="curl: (28) Connection timed out after 24000 ms", backend="curl_cffi")


async def test_connect_timeout_quarantines_url_after_threshold() -> None:
    cfg = _config(urls=["http://u:p@a:1"], failure_threshold=2, quarantine_sec=60)
    transport = _FakeTransport([_TIMEOUT])
    client = _client(cfg, transport)

    payload, status, err = await client.fetch_vehicle_detail("1")
    assert status == 0 and payload is None and "timed out" in (err or "")
    assert client.proxy_pool.quarantined_now() == 0  # 1-я ошибка — только серия

    await client.fetch_vehicle_detail("2")
    assert client.proxy_pool.quarantined_now() == 1  # 2-я подряд → карантин
    m = client.snapshot_metrics()
    assert m["proxy_failures_total"] == 2
    assert m["proxy_quarantine_events"] == 1
    assert m["proxy_urls_total"] == 1


async def test_success_response_clears_quarantine() -> None:
    cfg = _config(urls=["http://u:p@a:1"], failure_threshold=1, quarantine_sec=60)
    transport = _FakeTransport([_TIMEOUT, TransportResponse(status=200, json_data={"Id": "7"}, backend="curl_cffi")])
    client = _client(cfg, transport)

    await client.fetch_vehicle_detail("1")
    assert client.proxy_pool.quarantined_now() == 1
    payload, status, _ = await client.fetch_vehicle_detail("2")
    assert status == 200 and payload == {"Id": "7"}
    assert client.proxy_pool.quarantined_now() == 0


async def test_legit_404_does_not_quarantine_proxy() -> None:
    cfg = _config(urls=["http://u:p@a:1"], failure_threshold=1, quarantine_sec=60)
    transport = _FakeTransport([TransportResponse(status=404, text="gone", backend="curl_cffi")])
    client = _client(cfg, transport)

    _, status, _ = await client.fetch_vehicle_detail("1")
    assert status == 404
    assert client.proxy_pool.quarantined_now() == 0
    assert client.snapshot_metrics()["proxy_failures_total"] == 0


async def test_proxy_407_counts_as_proxy_failure() -> None:
    cfg = _config(urls=["http://u:p@a:1"], failure_threshold=1, quarantine_sec=60)
    transport = _FakeTransport([TransportResponse(status=407, text="proxy auth", backend="curl_cffi")])
    client = _client(cfg, transport)

    _, status, _ = await client.fetch_vehicle_detail("1")
    assert status == 407
    assert client.proxy_pool.quarantined_now() == 1


async def test_health_disabled_by_default_keeps_old_behaviour() -> None:
    cfg = _config(urls=["http://u:p@a:1"])  # без failure_threshold/quarantine_sec
    transport = _FakeTransport([_TIMEOUT])
    client = _client(cfg, transport)

    for i in range(5):
        await client.fetch_vehicle_detail(str(i))
    assert client.proxy_pool.health_enabled is False
    assert client.proxy_pool.quarantined_now() == 0
    assert client.snapshot_metrics()["proxy_failures_total"] == 5


async def test_snapshot_has_no_proxy_keys_when_pool_disabled() -> None:
    cfg = _config(urls=["http://u:p@a:1"], failure_threshold=1, quarantine_sec=60)
    cfg["proxy"]["enabled"] = False
    cfg["proxy"]["urls"] = []
    client = AsyncEncarClient(cfg, _log())
    assert "proxy_quarantined" not in client.snapshot_metrics()
