import pytest


@pytest.fixture(autouse=True)
def _wra_isolate_clean_read_rollout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Host env WRA_CLEAN_READ_PERCENT=0 disables clean read even when tests set WRA_CLEAN_READ_MODE=1."""
    monkeypatch.delenv("WRA_CLEAN_READ_PERCENT", raising=False)
