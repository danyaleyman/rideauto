"""Fetcher: асинхронный HTTP-клиент Encar с экспоненциальным backoff (retry)."""

from __future__ import annotations

import asyncio
import logging
import random
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import aiohttp

from scraper_pipeline.common.backoff import build_backoff_config
from scraper_pipeline.common.proxy_pool import ProxyPool
from scraper_pipeline.retry import BackoffConfig, sleep_backoff


def _proxy_url_and_auth(proxy: Optional[str]) -> Tuple[Optional[str], Optional[aiohttp.BasicAuth]]:
    """Часть прокси отвечает 407, если логин/пароль только в URL; aiohttp надёжнее с proxy_auth."""
    if not proxy:
        return None, None
    parsed = urllib.parse.urlsplit(proxy)
    if not parsed.hostname:
        return proxy, None
    if parsed.username is not None or parsed.password is not None:
        login = urllib.parse.unquote(parsed.username or "")
        password = urllib.parse.unquote(parsed.password or "")
        auth = aiohttp.BasicAuth(login, password)
        host = parsed.hostname
        port = parsed.port
        scheme = (parsed.scheme or "http").lower()
        netloc = f"{host}:{port}" if port else host
        return f"{scheme}://{netloc}", auth
    return proxy, None


class AsyncEncarClient:
    def __init__(
        self,
        config: dict,
        logger: logging.Logger,
    ):
        self.config = config
        self.log = logger
        http = config.get("http", {})
        self.list_url = "https://api.encar.com/search/car/list/general"
        self.base_api = "https://api.encar.com/v1/readside"
        self.conn_limit = http.get("conn_limit_per_host", 10)
        # sock_read: иначе при «залипшем» прокси чтение тела может не уложиться в total так, как ожидают.
        # sock_connect: CONNECT к HTTP-прокси без потолка иногда «висит» годами — отдельный лимит.
        _conn = float(http.get("timeout_connect", 10) or 10)
        self.timeout = aiohttp.ClientTimeout(
            total=http.get("timeout_total", 30),
            connect=_conn,
            sock_connect=_conn,
            sock_read=http.get("timeout_sock_read", 25),
        )
        # Внешний потолок на одну попытку (jitter + запрос + чтение тела). Иначе один await _request
        # может жить max_attempts * (total + backoff) и обходить asyncio.wait_for вокруг fetch_vehicle_detail.
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
        self.user_agents = config.get("user_agents", [])
        if not self.user_agents:
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ]
        proxy_cfg = config.get("proxy", {})
        proxy_urls = [str(u).strip() for u in (proxy_cfg.get("urls") or []) if str(u).strip()] if proxy_cfg.get("enabled") else []
        self.proxy_pool = ProxyPool(proxy_urls, rotation=str(proxy_cfg.get("rotation", "round_robin")))
        self._session: Optional[aiohttp.ClientSession] = None
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
        self._ua_index = (self._ua_index + 1) % len(self.user_agents)
        return self.user_agents[self._ua_index]

    async def _jitter(self) -> None:
        delay = random.uniform(self.jitter_min, self.jitter_max)
        await asyncio.sleep(delay)

    def snapshot_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

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

    async def __aenter__(self) -> "AsyncEncarClient":
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            trust_env=False,
            connector=aiohttp.TCPConnector(limit_per_host=self.conn_limit),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        origin: str = "https://www.encar.com",
    ) -> Tuple[Optional[dict], int, Optional[str]]:
        if not self._session:
            return None, 0, "no session"
        if self._cb_open_until_mono > time.monotonic():
            self._metric_inc("circuit_breaker_short_circuit")
            return None, 0, "circuit_breaker_open"
        h = dict(headers or {})
        h.setdefault("User-Agent", self._next_ua())
        h.setdefault("Accept", "application/json, text/javascript, */*; q=0.01")
        h.setdefault("Accept-Language", "en-US,en;q=0.9")
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
                    p_url, p_auth = _proxy_url_and_auth(proxy)
                    async with self._session.request(
                        method, url, headers=h, params=params, proxy=p_url, proxy_auth=p_auth
                    ) as resp:
                        status = int(resp.status)
                        retry_after = resp.headers.get("Retry-After")
                        if status in self.retry_statuses:
                            return "retry", None, status, f"status {status}", retry_after
                        if status != 200:
                            text = (await resp.text())[:500]
                            return "final", None, status, text, None
                        data = await resp.json()
                        return "final", data, 200, None, None

                kind, payload, st, err, retry_after = await asyncio.wait_for(_one_attempt(), timeout=hard)
                if kind == "retry":
                    self._metric_inc("retries_total")
                    if int(st or 0) == 429:
                        self._metric_inc("retry_status_429")
                    elif int(st or 0) == 407:
                        self._metric_inc("retry_status_407")
                    elif int(st or 0) >= 500:
                        self._metric_inc("retry_status_5xx")
                    self._record_failure_for_circuit_breaker(st, err)
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
                return payload, st, err
            except asyncio.TimeoutError as e:
                self._metric_inc("exceptions_timeout")
                self._record_failure_for_circuit_breaker(0, str(e))
                last_error = f"hard_deadline {hard:.0f}s ({e})"
                await sleep_backoff(self._backoff, attempt)
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientError as e:
                self._metric_inc("exceptions_client")
                self._record_failure_for_circuit_breaker(0, str(e))
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
