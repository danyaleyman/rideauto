from fastapi_app.image_service import _upstream_body_kind, host_matches_allowed, parse_allowed_hosts


def test_host_matches_allowed_exact_and_wildcard() -> None:
    allowed = parse_allowed_hosts("ci.encar.com,*.autoimg.cn,*.che168.com,che168.com")
    assert host_matches_allowed("ci.encar.com", allowed)
    assert host_matches_allowed("erscglobal1.autoimg.cn", allowed)
    assert host_matches_allowed("autoimg.cn", allowed)
    assert host_matches_allowed("global.che168.com", allowed)
    assert host_matches_allowed("che168.com", allowed)
    assert not host_matches_allowed("evil.autoimg.cn.evil.com", allowed)
    assert not host_matches_allowed("example.com", allowed)


def test_upstream_body_kind_sniff() -> None:
    assert _upstream_body_kind(b"") == "empty"
    assert _upstream_body_kind(b"   <!DOCTYPE html><html>") == "html"
    assert _upstream_body_kind(b'{"err":1}') == "text_or_markup"
    assert _upstream_body_kind(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "jpeg"
    assert _upstream_body_kind(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") == "png"
