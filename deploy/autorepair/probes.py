"""Пробы всех звеньев цепочки (docker + HTTP)."""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from .chain import topo_order
from .config import AutorepairConfig


@dataclass
class ProbeResult:
    component_id: str
    ok: bool
    detail: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def _run(cmd: list[str], cwd: str, timeout: int = 60) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as exc:
        return 127, "", str(exc)


def _http_json(url: str, timeout: int = 12) -> tuple[bool, Any, str]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status >= 400:
                return False, None, f"HTTP {resp.status}"
            try:
                return True, json.loads(body), body[:200]
            except json.JSONDecodeError:
                return resp.status < 400, body, body[:200]
    except urllib.error.HTTPError as exc:
        return False, None, f"HTTP {exc.code}"
    except Exception as exc:
        return False, None, str(exc)[:200]


def probe_compose_health(cfg: AutorepairConfig) -> dict[str, ProbeResult]:
    """Статус healthcheck docker compose по сервисам."""
    code, out, err = _run(
        ["docker", "compose", "ps", "--format", "json"],
        str(cfg.project_root),
        timeout=45,
    )
    results: dict[str, ProbeResult] = {}
    by_service: dict[str, dict[str, Any]] = {}

    if code == 0 and out.strip():
        for line in out.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            svc = (row.get("Service") or row.get("Name") or "").strip()
            if svc:
                by_service[svc] = row

    for comp in topo_order():
        if not comp.compose_service:
            continue
        row = by_service.get(comp.compose_service, {})
        state = (row.get("State") or row.get("Status") or "").lower()
        health = (row.get("Health") or "").lower()
        running = "running" in state or state == "running"
        healthy = health in {"", "healthy"} and running
        if not row:
            results[comp.id] = ProbeResult(comp.id, False, "container not in compose ps")
        elif not running:
            results[comp.id] = ProbeResult(comp.id, False, f"state={state or 'unknown'}")
        elif health and health not in ("healthy", ""):
            results[comp.id] = ProbeResult(comp.id, False, f"health={health}")
        else:
            results[comp.id] = ProbeResult(comp.id, True, f"running health={health or 'n/a'}")

    if code != 0 and not results:
        msg = (err or out or "compose ps failed")[:200]
        for comp in topo_order():
            if comp.compose_service:
                results[comp.id] = ProbeResult(comp.id, False, msg)
    return results


def probe_api_deep(cfg: AutorepairConfig) -> ProbeResult:
    ok, data, detail = _http_json(cfg.api_health_url)
    if not ok or not isinstance(data, dict):
        return ProbeResult("api", False, detail or "api health unreachable")
    status = data.get("status", "unknown")
    checks = data.get("checks") or {}
    pg_ok = (checks.get("postgres") or {}).get("ok")
    redis_ok = (checks.get("redis") or {}).get("ok", True)
    meili = checks.get("meilisearch") or {}
    meili_ok = meili.get("ok")
    meili_stale = meili.get("stale")
    if status == "ok":
        return ProbeResult("api", True, "deep health ok", {"checks": checks})
    if status == "degraded" and pg_ok and redis_ok and meili_stale:
        return ProbeResult(
            "api",
            False,
            "meilisearch stale (index behind postgres)",
            {"checks": checks, "meili_stale": True},
        )
    return ProbeResult("api", False, f"status={status}", {"checks": checks})


def probe_web(cfg: AutorepairConfig) -> ProbeResult:
    ok, _, detail = _http_json(cfg.web_url, timeout=15)
    if ok:
        return ProbeResult("web", True, "web responds")
    return ProbeResult("web", False, detail or "web unreachable")


def probe_meili_http(cfg: AutorepairConfig) -> ProbeResult:
    ok, data, detail = _http_json(cfg.meili_health_url)
    if ok:
        return ProbeResult("meilisearch", True, "meili /health ok", {"body": data})
    return ProbeResult("meilisearch", False, detail or "meili unreachable")


def probe_edge(cfg: AutorepairConfig) -> ProbeResult:
    """Edge = публичный URL если задан, иначе web+api достаточно."""
    public = (cfg.web_url if "rideauto" in cfg.web_url else "").strip()
    if not public.startswith("http"):
        api_ok = probe_api_deep(cfg).ok
        web_ok = probe_web(cfg).ok
        return ProbeResult("edge", api_ok and web_ok, "local web+api")
    ok, _, detail = _http_json(public, timeout=15)
    return ProbeResult("edge", ok, detail or ("ok" if ok else "edge fail"))


def run_all_probes(cfg: AutorepairConfig) -> dict[str, ProbeResult]:
    out = probe_compose_health(cfg)
    if "api" not in out or out["api"].ok:
        api_pr = probe_api_deep(cfg)
        out["api"] = api_pr
    else:
        out.setdefault("api", ProbeResult("api", False, "skipped: compose unhealthy"))
    out["web"] = probe_web(cfg)
    if "meilisearch" in out and not out["meilisearch"].ok:
        meili_http = probe_meili_http(cfg)
        if meili_http.ok:
            out["meilisearch"] = meili_http
    out["edge"] = probe_edge(cfg)
    for comp in topo_order():
        out.setdefault(comp.id, ProbeResult(comp.id, False, "not probed"))
    return out
