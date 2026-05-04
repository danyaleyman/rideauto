from scraper_pipeline.che168.session_playwright import playwright_proxy_config


def test_playwright_proxy_with_auth():
    d = playwright_proxy_config("http://user:pass@proxy.example.com:8080")
    assert d is not None
    assert d["server"] == "http://proxy.example.com:8080"
    assert d["username"] == "user"
    assert d["password"] == "pass"


def test_playwright_proxy_empty():
    assert playwright_proxy_config("") is None
    assert playwright_proxy_config(None) is None
