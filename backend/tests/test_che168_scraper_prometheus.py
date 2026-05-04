import tempfile
from pathlib import Path

from scraper_pipeline.che168.scraper_prometheus import write_che168_scraper_prometheus_textfile


def test_write_prometheus_textfile():
    stats = {
        "session_refreshes": 2,
        "che168_cluster_method_vin": 1,
        "che168_cluster_method_attribute": 3,
        "che168_cluster_method_none": 10,
        "_che168_shape_samples": {("a", "b"), ("c", "d")},
        "che168_telemetry_cluster_near_miss_price": 5,
        "list_pages": 100,
        "saved": 40,
        "che168_search_empty_breaks": 2,
    }
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "che168.prom")
        write_che168_scraper_prometheus_textfile(p, stats)
        text = Path(p).read_text(encoding="utf-8")
        assert "che168_scraper_session_refresh_total 2" in text
        assert 'method="vin"' in text
        assert "che168_scraper_parser_shape_variants 2" in text
        assert "telemetry_cluster_near_miss_price" in text
