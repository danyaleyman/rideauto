"""Fetcher: асинхронный HTTP-клиент Encar с экспоненциальным backoff (retry)."""

from __future__ import annotations

import asyncio
import logging
import random
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import aiohttp

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
        self._backoff = BackoffConfig(
            base_sec=float(retry.get("backoff_base", 1)),
            max_sec=float(retry.get("backoff_max", 60)),
        )
        self.retry_statuses = set(retry.get("retry_statuses", [429, 500, 502, 503, 504]))
        self.user_agents = config.get("user_agents", [])
        if not self.user_agents:
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ]
        proxy_cfg = config.get("proxy", {})
        self.proxies = proxy_cfg.get("urls", []) if proxy_cfg.get("enabled") else []
        self._session: Optional[aiohttp.ClientSession] = None
        self._proxy_index = 0
        self._ua_index = 0

    def _next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        self._proxy_index = (self._proxy_index + 1) % len(self.proxies)
        return self.proxies[self._proxy_index]

    def _next_ua(self) -> str:
        self._ua_index = (self._ua_index + 1) % len(self.user_agents)
        return self.user_agents[self._ua_index]

    async def _jitter(self) -> None:
        delay = random.uniform(self.jitter_min, self.jitter_max)
        await asyncio.sleep(delay)

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
                    last_error = err or ""
                    last_http_status = st
                    await sleep_backoff(self._backoff, attempt, retry_after)
                    continue
                return payload, st, err
            except asyncio.TimeoutError as e:
                last_error = f"hard_deadline {hard:.0f}s ({e})"
                await sleep_backoff(self._backoff, attempt)
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientError as e:
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
        params = {"vehicleNo": urllib.parse.quote(plate_number)}
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
