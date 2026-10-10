"""HTTP transport: curl_cffi (Chrome TLS) с fallback на aiohttp."""

from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from scraper_pipeline.resilience.browser_profile import BrowserProfile, resolve_browser_profile

JsonLike = Union[dict, list, str, int, float, bool, None]


@dataclass
class TransportResponse:
    status: int
    text: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    json_data: Optional[Any] = None
    error: Optional[str] = None
    backend: str = ""


def split_proxy_url(proxy: Optional[str]) -> Tuple[Optional[str], Optional[Tuple[str, str]]]:
    """
    http(s)://user:pass@host:port → (http://host:port, (user, pass)).
    Совместимо с aiohttp proxy_auth и curl_cffi proxy_auth.
    """
    if not proxy:
        return None, None
    parsed = urllib.parse.urlsplit(str(proxy).strip())
    if not parsed.hostname:
        return str(proxy).strip(), None
    auth: Optional[Tuple[str, str]] = None
    if parsed.username is not None or parsed.password is not None:
        login = urllib.parse.unquote(parsed.username or "")
        password = urllib.parse.unquote(parsed.password or "")
        auth = (login, password)
        host = parsed.hostname
        port = parsed.port
        scheme = (parsed.scheme or "http").lower()
        netloc = f"{host}:{port}" if port else host
        return f"{scheme}://{netloc}", auth
    return str(proxy).strip(), None


def resolve_transport_backend(config: Mapping[str, Any]) -> str:
    http = config.get("http") if isinstance(config.get("http"), dict) else {}
    res = config.get("resilience") if isinstance(config.get("resilience"), dict) else {}
    raw = http.get("transport") if http.get("transport") is not None else res.get("transport")
    backend = str(raw or "curl_cffi").strip().lower() or "curl_cffi"
    if backend in ("curl", "cffi", "curl-cffi"):
        return "curl_cffi"
    if backend in ("aiohttp", "aio"):
        return "aiohttp"
    return backend


def resolve_transport_max_clients(
    config: Mapping[str, Any], *, conn_limit: Optional[int] = None
) -> int:
    """
    Сколько одновременных запросов держит curl_cffi-сессия (`AsyncSession(max_clients=...)`).

    curl_cffi по умолчанию `max_clients=10` — и это потолок НА ВСЮ СЕССИЮ (у Encar один
    `AsyncEncarClient` на все detail-воркеры), поэтому `http.concurrency > 10` не увеличивал
    темп, сколько бы живых прокси ни было. Прод-замер 2026-10-10 (одинаковая нагрузка:
    48 detail-запросов, conc=24, те же 22 KR-прокси): `AsyncSession()` → 2.2 req/s,
    `max_clients=64` → 17.1 req/s, `max_clients=128` → 18.8 req/s.

    `http.transport_max_clients`:
      * > 0 — использовать как есть (ставим с запасом над `http.concurrency`);
      * 0/пусто/нечисло — авто: `max(32, concurrency, conn_limit_per_host) * 2`.

    Неположительные значения не поддерживаются: curl_cffi создаёт пул curl-хэндлов строго
    по `max_clients` (`asyncio.LifoQueue(max_clients)` + `put_nowait` до `QueueFull`), поэтому
    при `max_clients <= 0` пул не ограничен и `init_pool()` зацикливается.
    """
    http = config.get("http") if isinstance(config.get("http"), dict) else {}
    if conn_limit is None:
        try:
            conn_limit = int(http.get("conn_limit_per_host", 10) or 10)
        except (TypeError, ValueError):
            conn_limit = 10
    raw = http.get("transport_max_clients")
    if raw not in (None, ""):
        try:
            val = int(raw)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            return val
    try:
        conc = int(http.get("concurrency", 0) or 0)
    except (TypeError, ValueError):
        conc = 0
    return max(32, conc, int(conn_limit or 0)) * 2


class AsyncHttpTransport:
    """
    Единый async HTTP слой для Encar/Che168.

    По умолчанию curl_cffi + BrowserProfile.impersonate (JA3 как у Chrome).
    Fallback: aiohttp (http.transport: aiohttp), если curl_cffi недоступен.
    """

    def __init__(
        self,
        config: Mapping[str, Any],
        logger: logging.Logger,
        *,
        profile: Optional[BrowserProfile] = None,
        source: str = "generic",
    ):
        self.config = dict(config or {})
        self.log = logger
        self.source = source
        self.profile = profile or resolve_browser_profile(self.config)
        http = self.config.get("http") if isinstance(self.config.get("http"), dict) else {}
        self.backend = resolve_transport_backend(self.config)
        self.timeout_total = float(http.get("timeout_total", 30) or 30)
        self.timeout_connect = float(http.get("timeout_connect", 10) or 10)
        self.timeout_sock_read = float(http.get("timeout_sock_read", 25) or 25)
        self.conn_limit = int(http.get("conn_limit_per_host", 10) or 10)
        # Явный потолок «в полёте» для curl_cffi-сессии (дефолт 10 невидимо резал темп).
        self.transport_max_clients = resolve_transport_max_clients(
            self.config, conn_limit=self.conn_limit
        )
        self._curl_session: Any = None
        self._aio_session: Any = None
        self._metrics: Dict[str, int] = {
            "transport_requests_total": 0,
            "transport_requests_ok": 0,
            "transport_exceptions": 0,
            "transport_backend_curl_cffi": 0,
            "transport_backend_aiohttp": 0,
            "transport_fallback_to_aiohttp": 0,
        }
        if self.backend == "curl_cffi":
            try:
                import curl_cffi  # noqa: F401
            except ImportError:
                self.log.warning(
                    "resilience: curl_cffi не установлен — fallback на aiohttp "
                    "(pip install curl_cffi)"
                )
                self.backend = "aiohttp"
                self._metrics["transport_fallback_to_aiohttp"] = 1

    @property
    def impersonate(self) -> str:
        return self.profile.impersonate

    def snapshot_metrics(self) -> Dict[str, int]:
        out = dict(self._metrics)
        out["impersonate"] = 0  # placeholder; string exported separately
        return out

    def metrics_for_prometheus(self) -> Dict[str, Any]:
        return {
            **self._metrics,
            "transport_backend": self.backend,
            "transport_impersonate": self.profile.impersonate,
            "transport_max_clients": int(self.transport_max_clients),
        }

    def _metric_inc(self, key: str, by: int = 1) -> None:
        self._metrics[key] = int(self._metrics.get(key, 0) or 0) + by

    async def __aenter__(self) -> "AsyncHttpTransport":
        if self.backend == "curl_cffi":
            from curl_cffi.requests import AsyncSession

            self._curl_session = AsyncSession(max_clients=self.transport_max_clients)
            self._metric_inc("transport_backend_curl_cffi", 0)  # mark presence
            self.log.info(
                "Transport[%s]: curl_cffi impersonate=%s max_clients=%s (conn_limit_per_host=%s)",
                self.source,
                self.profile.impersonate,
                self.transport_max_clients,
                self.conn_limit,
            )
        else:
            import aiohttp

            timeout = aiohttp.ClientTimeout(
                total=self.timeout_total,
                connect=self.timeout_connect,
                sock_connect=self.timeout_connect,
                sock_read=self.timeout_sock_read,
            )
            self._aio_session = aiohttp.ClientSession(
                timeout=timeout,
                trust_env=False,
                connector=aiohttp.TCPConnector(limit_per_host=self.conn_limit),
            )
            self.log.info("Transport[%s]: aiohttp (no TLS impersonation)", self.source)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._curl_session is not None:
            try:
                await self._curl_session.close()
            except Exception:
                pass
            self._curl_session = None
        if self._aio_session is not None:
            try:
                await self._aio_session.close()
            except Exception:
                pass
            self._aio_session = None

    def merge_headers(
        self,
        headers: Optional[Mapping[str, str]] = None,
        *,
        use_profile_ua: bool = True,
    ) -> Dict[str, str]:
        h = dict(self.profile.default_headers()) if use_profile_ua else {}
        if headers:
            for k, v in headers.items():
                if v is not None:
                    h[str(k)] = str(v)
        if use_profile_ua:
            # Profile UA wins over random rotation for TLS coherence.
            h["User-Agent"] = self.profile.user_agent
        return h

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
        cookies: Optional[Mapping[str, str]] = None,
        proxy: Optional[str] = None,
        expect_json: bool = True,
        allow_redirects: bool = True,
        use_profile_ua: bool = True,
    ) -> TransportResponse:
        self._metric_inc("transport_requests_total")
        h = self.merge_headers(headers, use_profile_ua=use_profile_ua)
        qp: Optional[Dict[str, str]] = None
        if params:
            qp = {str(k): str(v) for k, v in params.items() if v is not None}
        ck = {str(k): str(v) for k, v in (cookies or {}).items() if v is not None} or None

        try:
            if self.backend == "curl_cffi":
                resp = await self._request_curl(
                    method, url, headers=h, params=qp, cookies=ck, proxy=proxy, allow_redirects=allow_redirects
                )
            else:
                resp = await self._request_aio(
                    method, url, headers=h, params=qp, cookies=ck, proxy=proxy, allow_redirects=allow_redirects
                )
        except Exception as e:
            self._metric_inc("transport_exceptions")
            return TransportResponse(status=0, text="", error=str(e), backend=self.backend)

        if resp.status == 200 and (resp.json_data is not None or not expect_json):
            self._metric_inc("transport_requests_ok")
        elif resp.status == 200 and expect_json and resp.error:
            pass
        elif resp.status == 200:
            self._metric_inc("transport_requests_ok")
        return resp

    async def _request_curl(
        self,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        params: Optional[Dict[str, str]],
        cookies: Optional[Dict[str, str]],
        proxy: Optional[str],
        allow_redirects: bool,
    ) -> TransportResponse:
        if self._curl_session is None:
            return TransportResponse(status=0, error="no session", backend="curl_cffi")
        self._metric_inc("transport_backend_curl_cffi")
        p_url, p_auth = split_proxy_url(proxy)
        timeout = max(self.timeout_total, self.timeout_sock_read + self.timeout_connect)
        r = await self._curl_session.request(
            method.upper(),
            url,
            headers=headers,
            params=params,
            cookies=cookies,
            proxy=p_url,
            proxy_auth=p_auth,
            impersonate=self.profile.impersonate,
            timeout=timeout,
            allow_redirects=allow_redirects,
            default_headers=False,
        )
        status = int(getattr(r, "status_code", 0) or 0)
        raw_headers = getattr(r, "headers", None) or {}
        hdrs = {str(k): str(v) for k, v in dict(raw_headers).items()}
        text = ""
        try:
            text = r.text or ""
        except Exception:
            text = ""
        json_data = None
        err = None
        try:
            json_data = r.json()
        except Exception as e:
            err = f"json_error {e}" if status == 200 else None
        return TransportResponse(
            status=status,
            text=text,
            headers=hdrs,
            json_data=json_data,
            error=err,
            backend="curl_cffi",
        )

    async def _request_aio(
        self,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        params: Optional[Dict[str, str]],
        cookies: Optional[Dict[str, str]],
        proxy: Optional[str],
        allow_redirects: bool,
    ) -> TransportResponse:
        if self._aio_session is None:
            return TransportResponse(status=0, error="no session", backend="aiohttp")
        import aiohttp

        self._metric_inc("transport_backend_aiohttp")
        p_url, auth_pair = split_proxy_url(proxy)
        p_auth = aiohttp.BasicAuth(auth_pair[0], auth_pair[1]) if auth_pair else None
        async with self._aio_session.request(
            method.upper(),
            url,
            headers=headers,
            params=params,
            cookies=cookies,
            proxy=p_url,
            proxy_auth=p_auth,
            allow_redirects=allow_redirects,
        ) as resp:
            status = int(resp.status)
            hdrs = {str(k): str(v) for k, v in resp.headers.items()}
            text = await resp.text()
            json_data = None
            err = None
            if status == 200:
                try:
                    json_data = await resp.json(content_type=None)
                except Exception as e:
                    err = f"json_error {e}"
            return TransportResponse(
                status=status,
                text=text,
                headers=hdrs,
                json_data=json_data,
                error=err,
                backend="aiohttp",
            )
