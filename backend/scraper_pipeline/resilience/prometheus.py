"""Prometheus textfile helpers for resilience metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def resilience_metric_lines(stats: Dict[str, Any], *, source: str) -> List[str]:
    """Строки Prometheus из client/policy/transport метрик в stats."""
    lines: List[str] = []
    src = "".join(c if c.isalnum() or c == "_" else "_" for c in source)

    cm = stats.get("client_metrics") if isinstance(stats.get("client_metrics"), dict) else {}
    tm = stats.get("transport_metrics") if isinstance(stats.get("transport_metrics"), dict) else {}
    if not tm and cm:
        # Clients may nest transport_* keys inside client_metrics.
        tm = {k: v for k, v in cm.items() if str(k).startswith("transport_")}
    pm = stats.get("policy_metrics") if isinstance(stats.get("policy_metrics"), dict) else {}

    impersonate = str(tm.get("transport_impersonate") or cm.get("transport_impersonate") or "unknown")
    backend = str(tm.get("transport_backend") or cm.get("transport_backend") or "unknown")
    safe_imp = "".join(c if c.isalnum() or c in "._-" else "_" for c in impersonate)
    safe_be = "".join(c if c.isalnum() or c in "._-" else "_" for c in backend)

    lines.append("# HELP scraper_transport_impersonateinfo TLS impersonate profile in use")
    lines.append("# TYPE scraper_transport_impersonateinfo gauge")
    lines.append(
        f'scraper_transport_impersonateinfo{{source="{src}",impersonate="{safe_imp}",backend="{safe_be}"}} 1'
    )

    for key, help_text in (
        ("transport_requests_total", "Transport requests"),
        ("transport_requests_ok", "Transport OK responses"),
        ("transport_exceptions", "Transport exceptions"),
        ("transport_fallback_to_aiohttp", "Fell back from curl_cffi to aiohttp"),
    ):
        val = int(tm.get(key, cm.get(key, 0)) or 0)
        mname = f"scraper_{key}"
        lines.append(f"# HELP {mname} {help_text}")
        lines.append(f"# TYPE {mname} counter")
        lines.append(f'{mname}{{source="{src}"}} {val}')

    age = float(pm.get("policy_session_age_seconds", stats.get("session_age_seconds", 0)) or 0)
    lines.append("# HELP scraper_session_age_seconds Age of current browser-derived session")
    lines.append("# TYPE scraper_session_age_seconds gauge")
    lines.append(f'scraper_session_age_seconds{{source="{src}"}} {age}')

    refresh = int(
        pm.get("policy_session_refresh_total", stats.get("session_refreshes", 0)) or 0
    )
    lines.append("# HELP scraper_session_refresh_total Session provider refresh count")
    lines.append("# TYPE scraper_session_refresh_total counter")
    lines.append(f'scraper_session_refresh_total{{source="{src}"}} {refresh}')

    challenge = int(pm.get("policy_challenge_detected_total", 0) or 0)
    lines.append("# HELP scraper_challenge_detected_total Hard challenge / CAPTCHA signals")
    lines.append("# TYPE scraper_challenge_detected_total counter")
    lines.append(f'scraper_challenge_detected_total{{source="{src}"}} {challenge}')

    deg = int(pm.get("policy_degrade_events", 0) or 0)
    lines.append("# HELP scraper_policy_degrade_events_total Concurrency degrade events")
    lines.append("# TYPE scraper_policy_degrade_events_total counter")
    lines.append(f'scraper_policy_degrade_events_total{{source="{src}"}} {deg}')

    clim = int(pm.get("policy_concurrency_limit", 0) or 0)
    if clim:
        lines.append("# HELP scraper_policy_concurrency_limit Adaptive concurrency limit")
        lines.append("# TYPE scraper_policy_concurrency_limit gauge")
        lines.append(f'scraper_policy_concurrency_limit{{source="{src}"}} {clim}')

    return lines


def append_resilience_metrics_to_textfile(path: str, stats: Dict[str, Any], *, source: str) -> None:
    """Дописывает resilience-метрики в существующий или новый .prom файл."""
    p = (path or "").strip()
    if not p:
        return
    extra = resilience_metric_lines(stats, source=source)
    out = Path(p)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if out.is_file():
        existing = out.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
    # Strip previous resilience block if re-written standalone — callers usually rewrite whole file.
    text = existing + "\n".join(extra) + "\n"
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
