from fastapi_app.image_service import host_matches_allowed, parse_allowed_hosts


def test_host_matches_allowed_exact_and_wildcard() -> None:
    allowed = parse_allowed_hosts("ci.encar.com,*.autoimg.cn,*.che168.com,che168.com")
    assert host_matches_allowed("ci.encar.com", allowed)
    assert host_matches_allowed("erscglobal1.autoimg.cn", allowed)
    assert host_matches_allowed("autoimg.cn", allowed)
    assert host_matches_allowed("global.che168.com", allowed)
    assert host_matches_allowed("che168.com", allowed)
    assert not host_matches_allowed("evil.autoimg.cn.evil.com", allowed)
    assert not host_matches_allowed("example.com", allowed)
