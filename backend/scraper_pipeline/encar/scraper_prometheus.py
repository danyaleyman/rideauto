from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def write_encar_scraper_prometheus_textfile(path: str, stats: Dict[str, Any]) -> None:
    p = (path or "").strip()
    if not p:
        return
    lines: list[str] = []

    lines.append("# HELP encar_scraper_list_pages_total List pages processed")
    lines.append("# TYPE encar_scraper_list_pages_total gauge")
    lines.append(f"encar_scraper_list_pages_total {int(stats.get('list_pages', 0) or 0)}")

    lines.append("# HELP encar_scraper_processed_total Cars processed this run")
    lines.append("# TYPE encar_scraper_processed_total gauge")
    lines.append(f"encar_scraper_processed_total {int(stats.get('processed', 0) or 0)}")

    lines.append("# HELP encar_scraper_saved_total Cars saved this run")
    lines.append("# TYPE encar_scraper_saved_total gauge")
    lines.append(f"encar_scraper_saved_total {int(stats.get('saved', 0) or 0)}")

    lines.append("# HELP encar_scraper_detail_fail_total Detail fetch failures")
    lines.append("# TYPE encar_scraper_detail_fail_total counter")
    lines.append(f"encar_scraper_detail_fail_total {int(stats.get('detail_fail', 0) or 0)}")

    lines.append("# HELP encar_scraper_parse_fail_total Parse failures")
    lines.append("# TYPE encar_scraper_parse_fail_total counter")
    lines.append(f"encar_scraper_parse_fail_total {int(stats.get('parse_fail', 0) or 0)}")

    lines.append("# HELP encar_scraper_detail_gone_total Listings marked gone/sold")
    lines.append("# TYPE encar_scraper_detail_gone_total counter")
    lines.append(f"encar_scraper_detail_gone_total {int(stats.get('detail_gone', 0) or 0)}")

    lines.append("# HELP encar_scraper_run_started_unixtime Run start time")
    lines.append("# TYPE encar_scraper_run_started_unixtime gauge")
    lines.append(f"encar_scraper_run_started_unixtime {int(stats.get('run_started_unixtime', 0) or 0)}")

    lines.append("# HELP encar_scraper_run_finished_unixtime Run finish time")
    lines.append("# TYPE encar_scraper_run_finished_unixtime gauge")
    lines.append(f"encar_scraper_run_finished_unixtime {int(stats.get('run_finished_unixtime', 0) or 0)}")

    for metric, help_text in (
        ("encar_scraper_cars_parsed_ok_total", "Cars parsed successfully"),
        ("encar_scraper_cars_with_images_total", "Parsed cars with non-empty gallery"),
        ("encar_scraper_cars_with_images_fallback_total", "Cars where image fallback from raw sources was used"),
        ("encar_scraper_cars_with_user_info_total", "Parsed cars with non-empty user info"),
    ):
        src = metric.replace("encar_scraper_", "").replace("_total", "")
        lines.append(f"# HELP {metric} {help_text}")
        lines.append(f"# TYPE {metric} gauge")
        lines.append(f"{metric} {int(stats.get(src, 0) or 0)}")

    cm = stats.get("client_metrics") if isinstance(stats.get("client_metrics"), dict) else {}
    if cm:
        mapping = {
            "requests_total": "encar_http_requests_total",
            "requests_ok": "encar_http_requests_ok_total",
            "retries_total": "encar_http_retries_total",
            "final_http_errors": "encar_http_final_http_errors_total",
            "exceptions_timeout": "encar_http_exceptions_timeout_total",
            "exceptions_client": "encar_http_exceptions_client_total",
            "circuit_breaker_opened": "encar_http_circuit_breaker_opened_total",
            "circuit_breaker_short_circuit": "encar_http_circuit_breaker_short_circuit_total",
            "retry_status_429": "encar_http_retry_status_429_total",
            "retry_status_407": "encar_http_retry_status_407_total",
            "retry_status_5xx": "encar_http_retry_status_5xx_total",
        }
        for src, metric in mapping.items():
            lines.append(f"# HELP {metric} Encar HTTP client metric {src}")
            lines.append(f"# TYPE {metric} counter")
            lines.append(f"{metric} {int(cm.get(src, 0) or 0)}")

    lines.append("")
    pp = Path(p)
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text("\n".join(lines), encoding="utf-8")
