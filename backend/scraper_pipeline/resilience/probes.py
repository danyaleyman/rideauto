"""Health probes: TLS transport / session / sample list."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scraper_pipeline.resilience.browser_profile import resolve_browser_profile
from scraper_pipeline.resilience.transport import AsyncHttpTransport


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeReport:
    source: str
    results: List[ProbeResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results) if self.results else False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "ok": self.ok,
            "results": [
                {"name": r.name, "ok": r.ok, "detail": r.detail, "meta": r.meta} for r in self.results
            ],
        }


async def probe_transport_tls(config: dict, log: logging.Logger, *, source: str = "generic") -> ProbeResult:
    profile = resolve_browser_profile(config)
    async with AsyncHttpTransport(config, log, profile=profile, source=source) as t:
        # Lightweight HTTPS endpoint; confirms impersonate path works.
        url = "https://www.cloudflare.com/cdn-cgi/trace"
        if source == "encar":
            url = "https://api.encar.com/search/car/list/general"
        elif source == "che168":
            url = "https://globalapi.che168.com/api/v1/brand"
        resp = await t.request("GET", url, expect_json=False, use_profile_ua=True)
        alive = int(resp.status or 0) > 0
        return ProbeResult(
            name="tls_transport",
            ok=alive,
            detail=f"backend={t.backend} impersonate={t.impersonate} status={resp.status} err={resp.error}",
            meta={"backend": t.backend, "impersonate": t.impersonate, "status": resp.status},
        )


async def probe_che168_session(config: dict, log: logging.Logger) -> ProbeResult:
    from scraper_pipeline.che168.client import AsyncChe168Client

    async with AsyncChe168Client(config, log) as client:
        data, status, err = await client.fetch_brands()
        has_sid = bool(client.get_initial_cookie("sessionid"))
        ok = int(status or 0) == 200 and data is not None
        return ProbeResult(
            name="che168_session",
            ok=ok,
            detail=f"status={status} has_sessionid={has_sid} err={err}",
            meta={"status": status, "has_sessionid": has_sid},
        )


async def probe_che168_list_nonempty(config: dict, log: logging.Logger, *, brandid: int = 276) -> ProbeResult:
    from scraper_pipeline.che168.client import AsyncChe168Client

    async with AsyncChe168Client(config, log) as client:
        data, status, err = await client.fetch_search(brandid=brandid, pageindex=1, pagesize=10)
        n = 0
        if isinstance(data, dict):
            layer = data.get("result") if isinstance(data.get("result"), dict) else data
            if isinstance(layer, dict):
                cl = layer.get("carlist") or layer.get("list") or []
                if isinstance(cl, list):
                    n = len(cl)
        ok = int(status or 0) == 200 and n > 0
        return ProbeResult(
            name="che168_list_nonempty",
            ok=ok,
            detail=f"status={status} items={n} err={err}",
            meta={"status": status, "items": n},
        )


async def probe_encar_list(config: dict, log: logging.Logger) -> ProbeResult:
    from scraper_pipeline.encar.client import AsyncEncarClient

    async with AsyncEncarClient(config, log) as client:
        data, status, err = await client.fetch_list_page(0, 10, "kor")
        n = 0
        if isinstance(data, dict):
            sr = data.get("SearchResults") or data.get("searchResults") or []
            if isinstance(sr, list):
                n = len(sr)
        ok = int(status or 0) == 200 and data is not None
        return ProbeResult(
            name="encar_list",
            ok=ok,
            detail=f"status={status} items={n} err={err}",
            meta={"status": status, "items": n},
        )


async def run_source_probes(source: str, config: dict, log: logging.Logger) -> ProbeReport:
    report = ProbeReport(source=source)
    report.results.append(await probe_transport_tls(config, log, source=source))
    if source == "che168":
        report.results.append(await probe_che168_session(config, log))
        report.results.append(await probe_che168_list_nonempty(config, log))
    elif source == "encar":
        report.results.append(await probe_encar_list(config, log))
    return report
