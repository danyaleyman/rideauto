import tempfile
from pathlib import Path

from scraper_pipeline.che168.scraper_prometheus import write_che168_scraper_prometheus_textfile


def test_write_prometheus_textfile():
    stats = {
        "run_started_unixtime": 1710000000,
        "run_finished_unixtime": 1710000060,
        "session_refreshes": 2,
        "che168_cluster_method_vin": 1,
        "che168_cluster_method_attribute": 3,
        "che168_cluster_method_none": 10,
        "_che168_shape_samples": {("a", "b"), ("c", "d")},
        "che168_telemetry_cluster_near_miss_price": 5,
        "list_pages": 100,
        "processed": 50,
        "saved": 40,
        "detail_fail": 3,
        "parse_fail": 1,
        "che168_search_empty_breaks": 2,
        "client_metrics": {
            "requests_total": 120,
            "requests_ok": 110,
            "retries_total": 15,
            "final_http_errors": 2,
            "exceptions_timeout": 1,
            "exceptions_client": 1,
            "circuit_breaker_opened": 1,
            "circuit_breaker_short_circuit": 4,
            "retry_status_429": 8,
            "retry_status_403": 2,
            "retry_status_407": 1,
            "retry_status_5xx": 4,
        },
    }
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "che168.prom")
        write_che168_scraper_prometheus_textfile(p, stats)
        text = Path(p).read_text(encoding="utf-8")
        assert "che168_scraper_session_refresh_total 2" in text
        assert 'method="vin"' in text
        assert "che168_scraper_parser_shape_variants 2" in text
        assert "telemetry_cluster_near_miss_price" in text
        assert "che168_scraper_processed_total 50" in text
        assert "che168_scraper_run_started_unixtime 1710000000" in text
        assert "che168_http_requests_total 120" in text
        assert "che168_http_circuit_breaker_short_circuit_total 4" in text
