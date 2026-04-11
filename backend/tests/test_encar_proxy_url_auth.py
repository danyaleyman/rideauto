"""Разбор URL прокси для aiohttp (407 при auth только в строке)."""

from scraper_pipeline.encar.client import _proxy_url_and_auth


def test_proxy_url_and_auth_embedded_credentials():
    url, auth = _proxy_url_and_auth("http://user:p%40ss@proxy.example.com:8080")
    assert url == "http://proxy.example.com:8080"
    assert auth is not None
    assert auth.login == "user"
    assert auth.password == "p@ss"


def test_proxy_url_and_auth_no_credentials():
    url, auth = _proxy_url_and_auth("http://proxy.example.com:8080")
    assert url == "http://proxy.example.com:8080"
    assert auth is None


def test_proxy_url_and_auth_none():
    assert _proxy_url_and_auth(None) == (None, None)
    assert _proxy_url_and_auth("") == (None, None)
