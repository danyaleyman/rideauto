"""Fetcher: асинхронный HTTP-клиент Encar с resilience Transport + backoff."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, Optional, Tuple

import aiohttp

from scraper_pipeline.common.backoff import build_backoff_config
from scraper_pipeline.common.proxy_pool import ProxyPool
from scraper_pipeline.resilience.browser_profile import resolve_browser_profile
from scraper_pipeline.resilience.policy import ResiliencePolicy, build_resilience_policy
from scraper_pipeline.resilience.transport import AsyncHttpTransport, split_proxy_url
from scraper_pipeline.retry import BackoffConfig, sleep_backoff


def _proxy_url_and_auth(proxy: Optional[str]) -> Tuple[Optional[str], Optional[aiohttp.BasicAuth]]:
    """Часть прокси отвечает 407, если логин/пароль только в URL; aiohttp надёжнее с proxy_auth."""
    p_url, auth_pair = split_proxy_url(proxy)
    if not auth_pair:
        return p_url, None
    return p_url, aiohttp.BasicAuth(auth_pair[0], auth_pair[1])


class AsyncEncarClient:
    def __init__(
        self,
        config: dict,
        logger: logging.Logger,
        *,
        policy: Optional[ResiliencePolicy] = None,
    ):
        self.config = config
        self.log = logger
        http = config.get("http", {})
        self.list_url = "https://api.encar.com/search/car/list/general"
        self.base_api = "https://api.encar.com/v1/readside"
        self.conn_limit = http.get("conn_limit_per_host", 10)
        _conn = float(http.get("timeout_connect", 10) or 10)
        self.timeout = aiohttp.ClientTimeout(
            total=http.get("timeout_total", 30),
            connect=_conn,
            sock_connect=_conn,
            sock_read=http.get("timeout_sock_read", 25),
        )
        _per = http.get("hard_deadline_per_attempt_sec")
        self._hard_deadline_per_attempt: Optional[float] = float(_per) if _per is not None else None
        if self._hard_deadline_per_attempt is not None and self._hard_deadline_per_attempt <= 0:
            self._hard_deadline_per_attempt = None
        self.jitter_min = http.get("request_jitter_min", 0.1)
        self.jitter_max = http.get("request_jitter_max", 0.5)
        retry = config.get("retry", {})
        self.max_attempts = retry.get("max_attempts", 5)
        self._backoff: BackoffConfig = build_backoff_config(config.get("retry", {}) or {}, retry)
        self.retry_statuses = set(retry.get("retry_statuses", [429, 500, 502, 503, 504]))
        self.profile = resolve_browser_profile(config)
        # Coherent identity: profile UA primary; config list kept for aiohttp legacy only.
        self.user_agents = config.get("user_agents", [])
        if not self.user_agents:
            self.user_agents = [self.profile.user_agent]
        proxy_cfg = config.get("proxy", {})
        proxy_urls = [str(u).strip() for u in (proxy_cfg.get("urls") or []) if str(u).strip()] if proxy_cfg.get("enabled") else []
        # Health-quarantine мёртвых прокси: после N подряд connect-ошибок URL выпадает из
        # ротации на quarantine_sec (иначе round-robin раздаёт мёртвый URL всем 24 воркерам
        # и открывается общий CB — см. ProxyPool и инцидент 2026-10-10).
        self.proxy_pool = ProxyPool(
            proxy_urls,
            rotation=str(proxy_cfg.get("rotation", "round_robin")),
            failure_threshold=int(proxy_cfg.get("failure_threshold", 0) or 0),
            quarantine_sec=float(proxy_cfg.get("quarantine_sec", 0) or 0),
        )
        self._transport: Optional[AsyncHttpTransport] = None
        self.policy = policy or build_resilience_policy(config, source="encar", logger=logger)
        self._ua_index = 0
        self._metrics: Dict[str, int] = {
            "requests_total": 0,
            "requests_ok": 0,
            "retries_total": 0,
            "retry_status_429": 0,
            "retry_status_407": 0,
            "retry_status_5xx": 0,
            "final_http_errors": 0,
            "exceptions_timeout": 0,
            "exceptions_client": 0,
            "proxy_failures_total": 0,
            "circuit_breaker_opened": 0,
            "circuit_breaker_short_circuit": 0,
        }
        self._cb_fail_streak = 0
        self._cb_open_until_mono = 0.0
        self._cb_fail_streak_threshold = int(retry.get("circuit_breaker_fail_streak", 12) or 12)
        self._cb_open_sec = float(retry.get("circuit_breaker_open_sec", 90) or 90)
        raw_cb = retry.get("circuit_breaker_statuses", [407, 429, 500, 502, 503, 504])
        self._cb_statuses: set[int] = set()
        if isinstance(raw_cb, list):
            for x in raw_cb:
                try:
                    self._cb_statuses.add(int(x))
                except (TypeError, ValueError):
                    continue

    def _next_proxy(self) -> Optional[str]:
        return self.proxy_pool.next_url()

    def _next_ua(self) -> str:
        # Prefer profile UA for TLS coherence when using curl_cffi.
        if self._transport and self._transport.backend == "curl_cffi":
            return self.profile.user_agent
        self._ua_index = (self._ua_index + 1) % len(self.user_agents)
        return self.user_agents[self._ua_index]

    async def _jitter(self) -> None:
        mult = self.policy.jitter_multiplier() if self.policy else 1.0
        delay = random.uniform(self.jitter_min, self.jitter_max) * mult
        await asyncio.sleep(delay)

    def snapshot_metrics(self) -> Dict[str, int]:
        out = dict(self._metrics)
        if self._transport:
            tm = self._transport.metrics_for_prometheus()
            for k, v in tm.items():
                if isinstance(v, (int, float)):
                    out[str(k)] = int(v)
                else:
                    out[str(k)] = v  # type: ignore[assignment]
        if self.policy:
            for k, v in self.policy.snapshot_metrics().items():
                if isinstance(v, (int, float)):
                    out[str(k)] = int(v) if not isinstance(v, float) or v == int(v) else v  # type: ignore[assignment]
        if self.proxy_pool.enabled:
            for k, v in self.proxy_pool.snapshot().items():
                out[str(k)] = int(v)
        return out

    def snapshot_transport_metrics(self) -> Dict[str, Any]:
        if self._transport:
            return self._transport.metrics_for_prometheus()
        return {}

    def snapshot_policy_metrics(self) -> Dict[str, Any]:
        return self.policy.snapshot_metrics() if self.policy else {}

    def _metric_inc(self, key: str, by: int = 1) -> None:
        self._metrics[key] = int(self._metrics.get(key, 0) or 0) + by

    def _record_failure_for_circuit_breaker(self, status: int, err: Optional[str]) -> None:
        status_i = int(status or 0)
        if status_i and status_i not in self._cb_statuses:
            return
        self._cb_fail_streak += 1
        if self._cb_fail_streak >= max(1, self._cb_fail_streak_threshold):
            self._cb_open_until_mono = time.monotonic() + max(1.0, self._cb_open_sec)
            self._cb_fail_streak = 0
            self._metric_inc("circuit_breaker_opened")
            self.log.warning(
                "Encar circuit breaker: open %.0fs after failures (status=%s err=%s)",
                self._cb_open_sec,
                status_i,
                (err or "")[:120],
            )

    def _record_success_for_circuit_breaker(self) -> None:
        self._cb_fail_streak = 0

    def _proxy_failed(self, proxy: Optional[str], reason: str) -> None:
        """Connect-ошибка конкретного прокси → health-карантин (см. ProxyPool).

        Вызывать только на транспортных сбоях (status=0 / hard deadline) и 407 — т.е. когда
        виноват URL, а не Encar. Обычные 429/5xx — это сайт, прокси не наказываем.
        """
        if not proxy:
            return
        self._metric_inc("proxy_failures_total")
        if not self.proxy_pool.mark_failure(proxy):
            return
        host = split_proxy_url(proxy)[0] or "?"
        self.log.warning(
            "Encar proxy quarantine: %s ушёл в карантин на %.0fs после %d подряд connect-ошибок (%s); в карантине %d/%d",
            host,
            self.proxy_pool.quarantine_sec,
            self.proxy_pool.failure_threshold,
            (reason or "")[:70],
            self.proxy_pool.quarantined_now(),
            len(self.proxy_pool.all()),
        )

    async def __aenter__(self) -> "AsyncEncarClient":
        self._transport = AsyncHttpTransport(
            self.config, self.log, profile=self.profile, source="encar"
        )
        await self._transport.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._transport:
            await self._transport.__aexit__(*args)
            self._transport = None

    async def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        origin: str = "https://www.encar.com",
    ) -> Tuple[Optional[dict], int, Optional[str]]:
        if not self._transport:
            return None, 0, "no session"
        if self._cb_open_until_mono > time.monotonic():
            self._metric_inc("circuit_breaker_short_circuit")
            return None, 0, "circuit_breaker_open"
        h = dict(headers or {})
        h.setdefault("User-Agent", self._next_ua())
        h.setdefault("Accept", "application/json, text/javascript, */*; q=0.01")
        h.setdefault("Accept-Language", self.profile.accept_language)
        h.setdefault("Origin", origin)
        h.setdefault("Referer", origin + "/")
        last_error: Optional[str] = None
        last_http_status: int = 0
        hard = self._hard_deadline_per_attempt
        if hard is None:
            http_cfg = self.config.get("http", {}) or {}
            tot = float(http_cfg.get("timeout_total", 30) or 30)
            sr = float(http_cfg.get("timeout_sock_read", 25) or 25)
            c = float(http_cfg.get("timeout_connect", 10) or 10)
            hard = max(tot, sr) + c + 8.0
        for attempt in range(self.max_attempts):
            self._metric_inc("requests_total")
            proxy = self._next_proxy()
            await self._jitter()
            try:

                async def _one_attempt() -> Tuple[str, Optional[dict], int, Optional[str], Optional[str]]:
                    tr = await self._transport.request(
                        method,
                        url,
                        headers=h,
                        params=params,
                        proxy=proxy,
                        expect_json=True,
                        use_profile_ua=True,
                    )
                    status = int(tr.status or 0)
                    retry_after = tr.headers.get("Retry-After") or tr.headers.get("retry-after")
                    if tr.error and status == 0:
                        raise aiohttp.ClientError(tr.error)
                    if status in self.retry_statuses:
                        return "retry", None, status, f"status {status}", retry_after
                    if status != 200:
                        text = (tr.text or "")[:500]
                        return "final", None, status, text or tr.error, None
                    if tr.json_data is None and tr.error:
                        return "final", None, 200, tr.error, None
                    data = tr.json_data if isinstance(tr.json_data, dict) else tr.json_data
                    if data is not None and not isinstance(data, dict):
                        return "final", None, 200, "non_object_json", None
                    return "final", data, 200, None, None  # type: ignore[return-value]

                kind, payload, st, err, retry_after = await asyncio.wait_for(_one_attempt(), timeout=hard)
                if self.policy:
                    self.policy.record_http_status(st)
                if int(st or 0) not in (0, 407):
                    # Прокси довёл запрос до HTTP-ответа Encar (в т.ч. 429/5xx, 404) → он живой.
                    self.proxy_pool.mark_success(proxy)
                if kind == "retry":
                    self._metric_inc("retries_total")
                    if int(st or 0) == 429:
                        self._metric_inc("retry_status_429")
                    elif int(st or 0) == 407:
                        self._metric_inc("retry_status_407")
                    elif int(st or 0) >= 500:
                        self._metric_inc("retry_status_5xx")
                    self._record_failure_for_circuit_breaker(st, err)
                    if int(st or 0) == 407:
                        # 407 = прокси-ошибка (auth/битый туннель): виноват URL, а не Encar.
                        self._proxy_failed(proxy, f"status {st}")
                    last_error = err or ""
                    last_http_status = st
                    await sleep_backoff(self._backoff, attempt, retry_after)
                    continue
                if int(st or 0) == 200 and payload is not None:
                    self._metric_inc("requests_ok")
                    self._record_success_for_circuit_breaker()
                elif int(st or 0) >= 400:
                    self._metric_inc("final_http_errors")
                    self._record_failure_for_circuit_breaker(st, err)
                    if int(st or 0) == 407:
                        # 407 может прийти и как final (если его нет в retry_statuses): виноват прокси.
                        self._proxy_failed(proxy, f"status {st}")
                return payload, st, err
            except asyncio.TimeoutError as e:
                self._metric_inc("exceptions_timeout")
                self._record_failure_for_circuit_breaker(0, str(e))
                self._proxy_failed(proxy, f"hard_deadline {hard:.0f}s")
                last_error = f"hard_deadline {hard:.0f}s ({e})"
                await sleep_backoff(self._backoff, attempt)
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, OSError) as e:
                self._metric_inc("exceptions_client")
                self._record_failure_for_circuit_breaker(0, str(e))
                self._proxy_failed(proxy, str(e))
                last_error = str(e)
                await sleep_backoff(self._backoff, attempt)
        return None, last_http_status, last_error

    async def fetch_list_page(
        self,
        offset: int,
        limit: int,
        car_type: str,
        q_suffix: str = "",
    ) -> Tuple[Optional[dict], int, Optional[str]]:
        car_type_flag = "N" if car_type == "for" else "Y"
        base = f"(And.Hidden.N._.CarType.{car_type_flag}.)"
        q = base[:-1] + q_suffix + ")" if q_suffix else base
        params = {
            "count": "true",
            "q": q,
            "sr": f"|ModifiedDate|{offset}|{limit}",
        }
        return await self._request(
            "GET",
            self.list_url,
            params=params,
            origin="https://www.encar.com",
        )

    async def fetch_vehicle_detail(self, car_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        url = f"{self.base_api}/vehicle/{car_id}"
        params = {
            "include": "ADVERTISEMENT,CATEGORY,CONDITION,CONTACT,MANAGE,OPTIONS,PHOTOS,SPEC,PARTNERSHIP,CENTER,VIEW"
        }
        return await self._request("GET", url, params=params, origin="https://fem.encar.com")

    async def fetch_record(self, car_id: str, plate_number: str) -> Tuple[Optional[dict], int, Optional[str]]:
        if not plate_number:
            return None, 0, "no plate"
        url = f"{self.base_api}/record/vehicle/{car_id}/open"
        params = {"vehicleNo": plate_number}
        return await self._request("GET", url, params=params, origin="https://fem.encar.com")

    async def fetch_diagnosis(self, car_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        url = f"{self.base_api}/diagnosis/vehicle/{car_id}"
        return await self._request("GET", url, origin="https://fem.encar.com")

    async def fetch_inspection(self, car_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        url = f"{self.base_api}/inspection/vehicle/{car_id}"
        return await self._request("GET", url, origin="https://fem.encar.com")

    async def fetch_sellingpoint(self, car_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        url = f"{self.base_api}/diagnosis/vehicle/{car_id}/sellingpoint"
        return await self._request("GET", url, origin="https://fem.encar.com")

    async def fetch_user(self, user_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        if not user_id:
            return None, 0, "no user id"
        url = f"{self.base_api}/user/{user_id}"
        return await self._request("GET", url, origin="https://fem.encar.com")
