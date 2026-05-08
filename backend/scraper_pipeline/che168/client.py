"""Асинхронный HTTP-клиент Che168 Global API (globalapi.che168.com)."""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from typing import Any, Dict, Optional, Tuple

import aiohttp

from scraper_pipeline.common.backoff import build_backoff_config
from scraper_pipeline.common.proxy_pool import ProxyPool
from scraper_pipeline.encar.client import _proxy_url_and_auth
from scraper_pipeline.retry import BackoffConfig, sleep_backoff


def ensure_che168_deviceid(config: dict, log: Optional[logging.Logger] = None) -> str:
    """
    Che168 API требует query deviceid. Если в конфиге пусто — подставляем случайный UUID v4
    (без ручного CHE168_DEVICE_ID). Для долгоживущей сессии лучше зафиксировать значение в YAML.
    """
    ch = config.setdefault("che168", {})
    cur = str(ch.get("deviceid", "") or "").strip()
    if cur:
        return cur
    dev = str(uuid.uuid4())
    ch["deviceid"] = dev
    if log:
        log.info(
            "Che168: пустой che168.deviceid — сгенерирован случайный UUID "
            "(для стабильной сессии задайте CHE168_DEVICE_ID или che168.deviceid в YAML)"
        )
    return dev


class AsyncChe168Client:
    """
    Базовый URL: https://globalapi.che168.com/api/v1/

    Общие query: _appid, deviceid, language (см. backend/che168/README.md).
    """

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.log = logger
        ensure_che168_deviceid(config, logger)
        ch = config.get("che168", {}) or {}
        http = config.get("http", {}) or {}
        self.base_url = str(ch.get("base_url", "https://globalapi.che168.com/api/v1")).rstrip("/")
        self._appid = str(ch.get("app_id", "global.pc"))
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
        retry = ch.get("retry") if isinstance(ch.get("retry"), dict) else {}
        if not retry:
            retry = config.get("retry", {}) or {}
        self.max_attempts = int(retry.get("max_attempts", 5) or 5)
        self._backoff: BackoffConfig = build_backoff_config(config.get("retry", {}) or {}, retry)
        self.retry_statuses = set(retry.get("retry_statuses", [429, 500, 502, 503, 504]))
        self.user_agents = config.get("user_agents", [])
        if not self.user_agents:
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        proxy_cfg = ch.get("proxy") if isinstance(ch.get("proxy"), dict) else {}
        if not proxy_cfg:
            proxy_cfg = config.get("proxy", {}) or {}
        sticky = str(ch.get("_session_proxy_url") or "").strip()
        if sticky:
            # Куки из Playwright получены на этом egress — ротация других прокси сбросит сессию.
            self.proxy_pool = ProxyPool([sticky], rotation="round_robin")
            self.log.info("Che168 HTTP: зафиксирован 1 прокси (совпадает с браузерным bootstrap)")
        elif proxy_cfg.get("enabled"):
            urls = [str(u).strip() for u in (proxy_cfg.get("urls") or []) if str(u).strip()]
            # Сессия Che168 (sessionid/куки) привязана к IP — по умолчанию один sticky egress.
            sticky_session = proxy_cfg.get("sticky_session", True)
            if urls and sticky_session:
                self.proxy_pool = ProxyPool([urls[0]], rotation="round_robin")
                if len(urls) > 1:
                    self.log.warning(
                        "Che168 HTTP: proxy.sticky_session=true — используется только urls[0]; "
                        "ещё %s URL игнорируются (смена IP сбросит сессию)",
                        len(urls) - 1,
                    )
            else:
                self.proxy_pool = ProxyPool(urls, rotation=str(proxy_cfg.get("rotation", "round_robin")))
        else:
            self.proxy_pool = ProxyPool([], rotation="round_robin")
        self._session: Optional[aiohttp.ClientSession] = None
        self._proxy_index = 0
        self._ua_index = 0
        self._last_rate_sleep_sec = 0.0
        self._metrics: Dict[str, int] = {
            "requests_total": 0,
            "requests_ok": 0,
            "retries_total": 0,
            "retry_status_429": 0,
            "retry_status_403": 0,
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
        self._cb_fail_streak_threshold = int(ch.get("circuit_breaker_fail_streak", 12) or 12)
        self._cb_open_sec = float(ch.get("circuit_breaker_open_sec", 90) or 90)
        raw_cb = ch.get("circuit_breaker_statuses", [403, 407, 429, 500, 502, 503, 504])
        self._cb_statuses: set[int] = set()
        if isinstance(raw_cb, list):
            for x in raw_cb:
                try:
                    self._cb_statuses.add(int(x))
                except (TypeError, ValueError):
                    continue

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
            self.proxy_pool = ProxyPool([sticky], rotation="round_robin")
        elif proxy_cfg.get("enabled"):
            urls = [str(u).strip() for u in (proxy_cfg.get("urls") or []) if str(u).strip()]
            if urls and proxy_cfg.get("sticky_session", True):
                self.proxy_pool = ProxyPool([urls[0]], rotation="round_robin")
            else:
                self.proxy_pool = ProxyPool(urls, rotation=str(proxy_cfg.get("rotation", "round_robin")))
        else:
            self.proxy_pool = ProxyPool([], rotation="round_robin")

    def get_initial_cookie(self, name: str) -> Optional[str]:
        return self._initial_cookies.get(name)

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
                "Che168 circuit breaker: open %.0fs after failures (status=%s err=%s)",
                self._cb_open_sec,
                status_i,
                (err or "")[:120],
            )

    def _record_success_for_circuit_breaker(self) -> None:
        self._cb_fail_streak = 0

    def _next_proxy(self) -> Optional[str]:
        return self.proxy_pool.next_url()

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
        if self._cb_open_until_mono > time.monotonic():
            self._metric_inc("circuit_breaker_short_circuit")
            return None, 0, "circuit_breaker_open"
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
            self._metric_inc("requests_total")
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
                    self._metric_inc("retries_total")
                    if int(st or 0) == 429:
                        self._metric_inc("retry_status_429")
                    elif int(st or 0) == 403:
                        self._metric_inc("retry_status_403")
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
        vehicle_list: int = 1,
        # Optional search filters (API-dependent, but required for segmentation).
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        mileage_min: Optional[int] = None,
        mileage_max: Optional[int] = None,
    ) -> Tuple[Optional[Any], int, Optional[str]]:
        params: Dict[str, Any] = {
            "brandid": brandid,
            "pageindex": pageindex,
            "pagesize": pagesize,
            "sort": sort,
            "vehicle_list": vehicle_list,
        }

        # Filters are added only when explicitly provided to avoid changing API defaults.
        if price_min is not None:
            params["price_min"] = price_min
        if price_max is not None:
            params["price_max"] = price_max
        if year_min is not None:
            params["year_min"] = year_min
        if year_max is not None:
            params["year_max"] = year_max
        if mileage_min is not None:
            params["mileage_min"] = mileage_min
        if mileage_max is not None:
            params["mileage_max"] = mileage_max

        return await self._request(
            "GET",
            "/search",
            params=params,
        )

    async def fetch_search_with_offset(
        self,
        *,
        brandid: int,
        offset: int,
        limit: int,
        sort: int = 0,
        vehicle_list: int = 1,
        # Optional search filters.
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        mileage_min: Optional[int] = None,
        mileage_max: Optional[int] = None,
    ) -> Tuple[Optional[Any], int, Optional[str]]:
        """
        Fallback pagination: some APIs accept offset/limit instead of pageindex/pagesize.

        If the endpoint doesn't support these params, you'll get empty results / non-200 responses.
        """
        params: Dict[str, Any] = {
            "brandid": brandid,
            "offset": offset,
            "limit": limit,
            "sort": sort,
            "vehicle_list": vehicle_list,
        }
        if price_min is not None:
            params["price_min"] = price_min
        if price_max is not None:
            params["price_max"] = price_max
        if year_min is not None:
            params["year_min"] = year_min
        if year_max is not None:
            params["year_max"] = year_max
        if mileage_min is not None:
            params["mileage_min"] = mileage_min
        if mileage_max is not None:
            params["mileage_max"] = mileage_max

        return await self._request("GET", "/search", params=params)

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

    async def fetch_global_detail_html(self, infoid: int | str) -> Tuple[Optional[str], int, Optional[str]]:
        """
        HTML страницы объявления на global.che168.com: в SSR/встроенном JSON часто есть
        полный список URL галереи (erscglobal*.autoimg.cn), которого нет в /carinfo JSON.
        """
        if not self._session:
            return None, 0, "no session"
        ch = self.config.get("che168", {}) or {}
        tmpl = str(ch.get("detail_page_url_template") or "{origin}/detail/{infoid}").strip()
        url = tmpl.format(origin=self._origin, infoid=str(infoid).strip())

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
            h: Dict[str, str] = {
                "User-Agent": self._next_ua(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": self._origin,
                "Referer": self._referer,
            }
            try:

                async def _one_html() -> Tuple[str, Optional[str], int, Optional[str], Optional[str]]:
                    p_url, p_auth = _proxy_url_and_auth(proxy)
                    async with self._session.get(
                        url,
                        headers=h,
                        cookies=self._initial_cookies or None,
                        proxy=p_url,
                        proxy_auth=p_auth,
                        allow_redirects=True,
                    ) as resp:
                        status = int(resp.status)
                        retry_after = resp.headers.get("Retry-After")
                        if status in self.retry_statuses:
                            return "retry", None, status, f"status {status}", retry_after
                        if status != 200:
                            frag = (await resp.text())[:400]
                            return "final", None, status, frag, None
                        await self._maybe_rate_limit_sleep(resp)
                        body = await resp.text()
                        return "final", body, 200, None, None

                kind, text, st, err, retry_after = await asyncio.wait_for(_one_html(), timeout=hard)
                if kind == "retry":
                    last_error = err or ""
                    last_http_status = st
                    await sleep_backoff(self._backoff, attempt, retry_after)
                    continue
                return text, st, err
            except asyncio.TimeoutError as e:
                last_error = f"hard_deadline {hard:.0f}s ({e})"
                await sleep_backoff(self._backoff, attempt)
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientError as e:
                last_error = str(e)
                await sleep_backoff(self._backoff, attempt)
        return None, last_http_status, last_error
