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

    lines.append("# HELP che168_scraper_search_empty_breaks_total Empty carlist page breaks")
    lines.append("# TYPE che168_scraper_search_empty_breaks_total counter")
    lines.append(f"che168_scraper_search_empty_breaks_total {int(stats.get('che168_search_empty_breaks', 0) or 0)}")

    lines.append("")
    out = Path(p)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(out)
