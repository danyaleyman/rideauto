"""Асинхронный HTTP-клиент Che168 Global API (globalapi.che168.com)."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, Optional, Tuple

import aiohttp

from scraper_pipeline.encar.client import _proxy_url_and_auth
from scraper_pipeline.retry import BackoffConfig, sleep_backoff


class AsyncChe168Client:
    """
    Базовый URL: https://globalapi.che168.com/api/v1/

    Общие query: _appid, deviceid, language (см. backend/che168/README.md).
    """

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.log = logger
        ch = config.get("che168", {}) or {}
        http = config.get("http", {}) or {}
        self.base_url = str(ch.get("base_url", "https://globalapi.che168.com/api/v1")).rstrip("/")
        self._appid = str(ch.get("app_id", "global.m"))
        self._deviceid = str(ch.get("deviceid", "") or "").strip()
        self._language = str(ch.get("language", "en"))
        self._origin = str(ch.get("origin", "https://global.che168.com")).rstrip("/")
        self._referer = str(ch.get("referer", f"{self._origin}/"))

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
        retry = config.get("retry", {}) or {}
        self.max_attempts = retry.get("max_attempts", 5)
        self._backoff = BackoffConfig(
            base_sec=float(retry.get("backoff_base", 1)),
            max_sec=float(retry.get("backoff_max", 60)),
        )
        self.retry_statuses = set(retry.get("retry_statuses", [429, 500, 502, 503, 504]))
        self.user_agents = config.get("user_agents", [])
        if not self.user_agents:
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        proxy_cfg = config.get("proxy", {}) or {}
        sticky = str(ch.get("_session_proxy_url") or "").strip()
        if sticky:
            # Куки из Playwright получены на этом egress — ротация других прокси сбросит сессию.
            self.proxies = [sticky]
            self.log.info("Che168 HTTP: зафиксирован 1 прокси (совпадает с браузерным bootstrap)")
        elif proxy_cfg.get("enabled"):
            urls = [str(u).strip() for u in (proxy_cfg.get("urls") or []) if str(u).strip()]
            # Сессия Che168 (sessionid/куки) привязана к IP — по умолчанию один sticky egress.
            sticky_session = proxy_cfg.get("sticky_session", True)
            if urls and sticky_session:
                self.proxies = [urls[0]]
                if len(urls) > 1:
                    self.log.warning(
                        "Che168 HTTP: proxy.sticky_session=true — используется только urls[0]; "
                        "ещё %s URL игнорируются (смена IP сбросит сессию)",
                        len(urls) - 1,
                    )
            else:
                self.proxies = urls
        else:
            self.proxies = []
        self._session: Optional[aiohttp.ClientSession] = None
        self._proxy_index = 0
        self._ua_index = 0
        self._last_rate_sleep_sec = 0.0

        self._initial_cookies = self._build_initial_cookies_dict(config)

    @staticmethod
    def _build_initial_cookies_dict(config: dict) -> Dict[str, str]:
        ch = config.get("che168", {}) or {}
        cookies = ch.get("cookies") if isinstance(ch.get("cookies"), dict) else {}
        initial: Dict[str, str] = {}
        for k, v in (cookies or {}).items():
            if v is not None and str(v).strip():
                initial[str(k)] = str(v)
        if ch.get("sessionid"):
            initial.setdefault("sessionid", str(ch["sessionid"]))
        if ch.get("is_overseas") is not None:
            initial["is_overseas"] = str(ch.get("is_overseas", "1"))
        else:
            initial.setdefault("is_overseas", "1")
        if ch.get("area") is not None:
            initial["area"] = str(ch.get("area", "0"))
        else:
            initial.setdefault("area", "0")
        return initial

    def reload_initial_cookies_from_config(self) -> None:
        """После Playwright bootstrap: подтянуть sessionid/куки из config в живую сессию aiohttp."""
        self._initial_cookies = self._build_initial_cookies_dict(self.config)
        sticky = str((self.config.get("che168") or {}).get("_session_proxy_url") or "").strip()
        proxy_cfg = self.config.get("proxy", {}) or {}
        if sticky:
            self.proxies = [sticky]
        elif proxy_cfg.get("enabled"):
            urls = [str(u).strip() for u in (proxy_cfg.get("urls") or []) if str(u).strip()]
            if urls and proxy_cfg.get("sticky_session", True):
                self.proxies = [urls[0]]
            else:
                self.proxies = urls
        else:
            self.proxies = []

    def get_initial_cookie(self, name: str) -> Optional[str]:
        return self._initial_cookies.get(name)

    def _next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        self._proxy_index = (self._proxy_index + 1) % len(self.proxies)
        return self.proxies[self._proxy_index]

    def _next_ua(self) -> str:
        self._ua_index = (self._ua_index + 1) % len(self.user_agents)
        return self.user_agents[self._ua_index]

    async def _jitter(self) -> None:
        await asyncio.sleep(random.uniform(self.jitter_min, self.jitter_max))

    async def _maybe_rate_limit_sleep(self, resp: aiohttp.ClientResponse) -> None:
        ch = self.config.get("che168", {}) or {}
        if not ch.get("respect_rate_limit_headers", True):
            return
        rem = resp.headers.get("X-RateLimit-Remaining") or resp.headers.get("RateLimit-Remaining")
        if rem is None:
            return
        try:
            if int(str(rem).strip()) > 0:
                return
        except ValueError:
            return
        reset = resp.headers.get("X-RateLimit-Reset") or resp.headers.get("RateLimit-Reset") or "2"
        try:
            delay = max(1.0, float(reset))
        except ValueError:
            delay = 2.0
        cap = float(ch.get("rate_limit_sleep_cap_sec", 60) or 60)
        delay = min(delay, cap)
        self._last_rate_sleep_sec = delay
        self.log.info("Che168 rate-limit: Remaining=0, sleep %.1fs", delay)
        await asyncio.sleep(delay)

    def _common_params(self) -> Dict[str, str]:
        if not self._deviceid:
            raise ValueError("che168.deviceid обязателен (UUID устройства для API)")
        return {
            "_appid": self._appid,
            "deviceid": self._deviceid,
            "language": self._language,
        }

    async def __aenter__(self) -> "AsyncChe168Client":
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            trust_env=False,
            connector=aiohttp.TCPConnector(limit_per_host=self.conn_limit),
            headers={"Accept": "application/json, text/plain, */*"},
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Any], int, Optional[str]]:
        if not self._session:
            return None, 0, "no session"
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        qp = dict(self._common_params())
        if params:
            for k, v in params.items():
                if v is None:
                    continue
                qp[str(k)] = str(v)

        h: Dict[str, str] = {
            "User-Agent": self._next_ua(),
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": self._origin,
            "Referer": self._referer,
        }
        last_error: Optional[str] = None
        last_http_status = 0
        hard = self._hard_deadline_per_attempt
        if hard is None:
            tot = float(self.config.get("http", {}).get("timeout_total", 30) or 30)
            sr = float(self.config.get("http", {}).get("timeout_sock_read", 25) or 25)
            c = float(self.config.get("http", {}).get("timeout_connect", 10) or 10)
            hard = max(tot, sr) + c + 8.0

        for attempt in range(self.max_attempts):
            proxy = self._next_proxy()
            await self._jitter()
            try:

                async def _one_attempt() -> Tuple[str, Optional[Any], int, Optional[str], Optional[str]]:
                    p_url, p_auth = _proxy_url_and_auth(proxy)
                    async with self._session.request(
                        method,
                        url,
                        headers=h,
                        params=qp,
                        cookies=self._initial_cookies or None,
                        proxy=p_url,
                        proxy_auth=p_auth,
                    ) as resp:
                        status = int(resp.status)
                        retry_after = resp.headers.get("Retry-After")
                        if status in self.retry_statuses:
                            return "retry", None, status, f"status {status}", retry_after
                        if status != 200:
                            text = (await resp.text())[:500]
                            return "final", None, status, text, None
                        await self._maybe_rate_limit_sleep(resp)
                        try:
                            data = await resp.json(content_type=None)
                        except Exception as e:
                            return "final", None, 200, f"json_error {e}", None
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

    async def fetch_brands(self) -> Tuple[Optional[Any], int, Optional[str]]:
        return await self._request("GET", "/brand")

    async def fetch_series_for_brand(self, brandid: int) -> Tuple[Optional[Any], int, Optional[str]]:
        """Список серий/модельного ряда по brandid (путь из che168.series_api_path, напр. /series)."""
        ch = self.config.get("che168", {}) or {}
        path = str(ch.get("series_api_path") or "").strip().lstrip("/")
        if not path:
            return None, 0, "series_api_path_empty"
        return await self._request("GET", path, params={"brandid": int(brandid)})

    async def fetch_search(
        self,
        *,
        brandid: int,
        pageindex: int,
        pagesize: int,
        sort: int = 0,
        vehicle_list: int = 0,
    ) -> Tuple[Optional[Any], int, Optional[str]]:
        return await self._request(
            "GET",
            "/search",
            params={
                "brandid": brandid,
                "pageindex": pageindex,
                "pagesize": pagesize,
                "sort": sort,
                "vehicle_list": vehicle_list,
            },
        )

    async def fetch_carinfo(self, infoid: int | str) -> Tuple[Optional[Any], int, Optional[str]]:
        return await self._request("GET", f"/carinfo/{infoid}")

    async def fetch_specparam(self, specid: int | str) -> Tuple[Optional[Any], int, Optional[str]]:
        return await self._request("GET", "/specparam", params={"specid": specid})

    async def fetch_specconfig(self, specid: int | str) -> Tuple[Optional[Any], int, Optional[str]]:
        return await self._request("GET", "/specconfig", params={"specid": specid})

    async def fetch_recommend(
        self,
        *,
        infoid: int | str,
        pageindex: int = 1,
        pagesize: int = 20,
    ) -> Tuple[Optional[Any], int, Optional[str]]:
        return await self._request(
            "GET",
            "/recommend",
            params={"infoid": infoid, "pageindex": pageindex, "pagesize": pagesize},
        )

    async def fetch_report_summary(self, dealerid: int | str, paramkey: str) -> Tuple[Optional[Any], int, Optional[str]]:
        if not paramkey:
            return None, 0, "no paramkey"
        return await self._request(
            "GET",
            "/report/summary",
            params={"dealerid": dealerid, "paramkey": paramkey},
        )
