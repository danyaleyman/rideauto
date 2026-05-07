"""Экспорт метрик прогона Che168 scraper в Prometheus textfile (node_exporter)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def write_che168_scraper_prometheus_textfile(path: str, stats: Dict[str, Any]) -> None:
    """
    Пишет *.prom для CHE168_PROMETHEUS_TEXTFILE или che168.prometheus_textfile_path.
    """
    p = (path or "").strip()
    if not p:
        return
    lines: list[str] = []

    lines.append("# HELP che168_scraper_session_refresh_total Playwright bootstrap on session hint")
    lines.append("# TYPE che168_scraper_session_refresh_total counter")
    lines.append(f"che168_scraper_session_refresh_total {int(stats.get('session_refreshes', 0) or 0)}")

    lines.append("# HELP che168_scraper_cluster_method_total Parsed listings by cluster method")
    lines.append("# TYPE che168_scraper_cluster_method_total counter")
    for method in ("vin", "attribute", "none"):
        v = int(stats.get(f"che168_cluster_method_{method}", 0) or 0)
        lines.append(f'che168_scraper_cluster_method_total{{method="{method}"}} {v}')

    shape_n = len(stats.get("_che168_shape_samples") or ())
    lines.append("# HELP che168_scraper_parser_shape_variants Distinct API shape fingerprints")
    lines.append("# TYPE che168_scraper_parser_shape_variants gauge")
    lines.append(f"che168_scraper_parser_shape_variants {float(shape_n)}")

    for k, v in sorted(stats.items()):
        if not k.startswith("che168_telemetry_"):
            continue
        if not isinstance(v, (int, float)):
            continue
        suffix = k.replace("che168_telemetry_", "", 1)
        safe = "".join(c if c.isalnum() or c == "_" else "_" for c in suffix)
        name = f"che168_scraper_telemetry_{safe}_total"
        lines.append(f"# HELP {name} Telemetry {suffix}")
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name} {int(v)}")

    lines.append("# HELP che168_scraper_list_pages_total Search pages processed")
    lines.append("# TYPE che168_scraper_list_pages_total gauge")
    lines.append(f"che168_scraper_list_pages_total {int(stats.get('list_pages', 0) or 0)}")

    lines.append("# HELP che168_scraper_saved_total Cars saved this run")
    lines.append("# TYPE che168_scraper_saved_total gauge")
    lines.append(f"che168_scraper_saved_total {int(stats.get('saved', 0) or 0)}")

    lines.append("# HELP che168_scraper_processed_total Cars processed this run")
    lines.append("# TYPE che168_scraper_processed_total gauge")
    lines.append(f"che168_scraper_processed_total {int(stats.get('processed', 0) or 0)}")

    lines.append("# HELP che168_scraper_detail_fail_total Detail fetch failures")
    lines.append("# TYPE che168_scraper_detail_fail_total counter")
    lines.append(f"che168_scraper_detail_fail_total {int(stats.get('detail_fail', 0) or 0)}")

    lines.append("# HELP che168_scraper_parse_fail_total Parse failures")
    lines.append("# TYPE che168_scraper_parse_fail_total counter")
    lines.append(f"che168_scraper_parse_fail_total {int(stats.get('parse_fail', 0) or 0)}")

    lines.append("# HELP che168_scraper_run_started_unixtime Run start time")
    lines.append("# TYPE che168_scraper_run_started_unixtime gauge")
    lines.append(f"che168_scraper_run_started_unixtime {int(stats.get('run_started_unixtime', 0) or 0)}")
    lines.append("# HELP che168_scraper_run_finished_unixtime Run finish time")
    lines.append("# TYPE che168_scraper_run_finished_unixtime gauge")
    lines.append(f"che168_scraper_run_finished_unixtime {int(stats.get('run_finished_unixtime', 0) or 0)}")

    lines.append("# HELP che168_scraper_search_empty_breaks_total Empty carlist page breaks")
    lines.append("# TYPE che168_scraper_search_empty_breaks_total counter")
    lines.append(f"che168_scraper_search_empty_breaks_total {int(stats.get('che168_search_empty_breaks', 0) or 0)}")

    cm = stats.get("client_metrics") if isinstance(stats.get("client_metrics"), dict) else {}
    if cm:
        for key in (
            "requests_total",
            "requests_ok",
            "retries_total",
            "final_http_errors",
            "exceptions_timeout",
            "exceptions_client",
            "circuit_breaker_opened",
            "circuit_breaker_short_circuit",
            "retry_status_429",
            "retry_status_403",
            "retry_status_407",
            "retry_status_5xx",
        ):
            val = int(cm.get(key, 0) or 0)
            mname = f"che168_http_{key}_total"
            if key in ("requests_total", "requests_ok"):
                mname = f"che168_http_{key}"
            lines.append(f"# HELP {mname} Che168 client metric {key}")
            lines.append(f"# TYPE {mname} counter")
            lines.append(f"{mname} {val}")

    lines.append("")
    out = Path(p)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(out)
