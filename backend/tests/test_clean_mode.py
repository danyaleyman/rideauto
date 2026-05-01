from clean_mode import clean_read_enabled_for_key, clean_read_rollout_percent


def test_clean_rollout_percent_bounds(monkeypatch):
    monkeypatch.setenv("WRA_CLEAN_READ_PERCENT", "150")
    assert clean_read_rollout_percent(default=10) == 100
    monkeypatch.setenv("WRA_CLEAN_READ_PERCENT", "-10")
    assert clean_read_rollout_percent(default=10) == 0


def test_clean_enabled_for_key_respects_percent(monkeypatch):
    monkeypatch.setenv("WRA_CLEAN_READ_MODE", "1")
    monkeypatch.setenv("WRA_CLEAN_READ_PERCENT", "0")
    assert clean_read_enabled_for_key("car-1") is False
    monkeypatch.setenv("WRA_CLEAN_READ_PERCENT", "100")
    assert clean_read_enabled_for_key("car-1") is True

