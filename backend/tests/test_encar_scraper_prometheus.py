import tempfile
from pathlib import Path

from scraper_pipeline.encar.scraper_prometheus import write_encar_scraper_prometheus_textfile


def test_write_encar_prometheus_textfile() -> None:
    stats = {
        "run_started_unixtime": 1710000000,
        "run_finished_unixtime": 1710000060,
        "list_pages": 80,
        "processed": 35,
        "saved": 30,
        "detail_fail": 2,
        "detail_gone": 3,
        "parse_fail": 1,
        "cars_parsed_ok": 29,
        "cars_with_images": 25,
        "cars_with_images_fallback": 4,
        "cars_with_user_info": 21,
        "client_metrics": {
            "requests_total": 210,
            "requests_ok": 201,
            "retries_total": 14,
            "final_http_errors": 4,
            "exceptions_timeout": 2,
            "exceptions_client": 1,
            "circuit_breaker_opened": 1,
            "circuit_breaker_short_circuit": 5,
            "retry_status_429": 6,
            "retry_status_407": 1,
            "retry_status_5xx": 7,
        },
    }
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "encar.prom")
        write_encar_scraper_prometheus_textfile(p, stats)
        text = Path(p).read_text(encoding="utf-8")
        assert "encar_scraper_list_pages_total 80" in text
        assert "encar_scraper_saved_total 30" in text
        assert "encar_scraper_cars_parsed_ok_total 29" in text
        assert "encar_scraper_cars_with_images_fallback_total 4" in text
        assert "encar_scraper_run_started_unixtime 1710000000" in text
        assert "encar_http_requests_total 210" in text
        assert "encar_http_circuit_breaker_short_circuit_total 5" in text
