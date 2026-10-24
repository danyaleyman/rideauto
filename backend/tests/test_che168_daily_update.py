from __future__ import annotations

import subprocess
from pathlib import Path

import che168_daily_update
from che168_daily_update import (
    _chunked,
    _external_infoid_from_car_id,
    _select_brand_window,
    _write_daily_prometheus_textfile,
    run_only_pending,
)


def test_select_brand_window_all_brands_when_no_limit() -> None:
    ids = [1, 2, 3, 4]
    assert _select_brand_window(ids, 0, 0) == (ids, 0)
    assert _select_brand_window(ids, 10, 3) == (ids, 0)


def test_select_brand_window_rotates() -> None:
    ids = list(range(1, 11))
    first, cursor = _select_brand_window(ids, 4, 0)
    assert first == [1, 2, 3, 4]
    assert cursor == 4
    second, cursor2 = _select_brand_window(ids, 4, cursor)
    assert second == [5, 6, 7, 8]
    third, cursor3 = _select_brand_window(ids, 4, cursor2)
    assert third == [9, 10, 1, 2]  # окно заворачивается по кругу
    assert cursor3 == 2


def test_select_brand_window_empty() -> None:
    assert _select_brand_window([], 5, 0) == ([], 0)


def test_external_infoid_from_car_id() -> None:
    assert _external_infoid_from_car_id("che168-12345") == "12345"
    assert _external_infoid_from_car_id(" 12345 ") == "12345"


def test_chunked_splits_ids() -> None:
    ids = ["a", "b", "c", "d", "e"]
    assert list(_chunked(ids, 2)) == [["a", "b"], ["c", "d"], ["e"]]


def test_write_daily_prometheus_textfile(tmp_path: Path) -> None:
    p = tmp_path / "che168_daily.prom"
    stats = {"new_cars_added": 7, "sold_cars_removed": 2, "pending_queue_size": 31}

    class _Log:
        def debug(self, *_a, **_k):
            return None

    _write_daily_prometheus_textfile(str(p), stats, _Log())
    text = p.read_text(encoding="utf-8")
    assert "che168_daily_new_cars 7" in text
    assert "che168_daily_sold_cars 2" in text
    assert "che168_daily_pending 31" in text


class _LogStub:
    """Минимальный логгер: копит отформатированные сообщения."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def _rec(self, fmt, *args, **_kwargs):
        self.messages.append(str(fmt) % args if args else str(fmt))

    info = debug = warning = error = _rec

    def exception(self, fmt, *args, **_kwargs):
        self._rec(fmt, *args)

    def text(self) -> str:
        return "\n".join(self.messages)


class _FakePopen:
    """Подмена subprocess.Popen: запоминает env/timeout и умеет «зависать»."""

    instances: list["_FakePopen"] = []
    timeout_on_wait = False
    returncode = 0

    def __init__(self, cmd, env=None, start_new_session=False):
        self.cmd = cmd
        self.env = dict(env or {})
        self.start_new_session = start_new_session
        self.pid = 4242
        self.wait_timeouts: list[float | None] = []
        self.killed = False
        _FakePopen.instances.append(self)

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        if _FakePopen.timeout_on_wait:
            raise subprocess.TimeoutExpired(cmd=self.cmd, timeout=timeout or 0)
        return _FakePopen.returncode

    def kill(self):
        self.killed = True


def _patch_popen(monkeypatch, *, timeout_on_wait: bool = False, returncode: int = 0) -> None:
    _FakePopen.instances = []
    _FakePopen.timeout_on_wait = timeout_on_wait
    _FakePopen.returncode = returncode
    monkeypatch.setattr(che168_daily_update.subprocess, "Popen", _FakePopen)


def test_run_only_pending_success_sets_skip_catalog_sync(tmp_path: Path, monkeypatch) -> None:
    _patch_popen(monkeypatch, returncode=0)
    monkeypatch.delenv("SKIP_POSTGRES_CATALOG_SYNC", raising=False)
    log = _LogStub()

    ok = run_only_pending(str(tmp_path / "cfg.yaml"), log, {"only_pending_timeout_sec": 120})

    assert ok is True
    proc = _FakePopen.instances[-1]
    assert proc.env["SKIP_POSTGRES_CATALOG_SYNC"] == "1"
    assert proc.start_new_session is True
    # Таймаут прокинут в wait() (в мс/с — как в конфиге).
    assert proc.wait_timeouts == [120]
    assert "--only-pending" in proc.cmd


def test_run_only_pending_respects_skip_catalog_sync_false(tmp_path: Path, monkeypatch) -> None:
    _patch_popen(monkeypatch, returncode=0)
    monkeypatch.delenv("SKIP_POSTGRES_CATALOG_SYNC", raising=False)

    ok = run_only_pending(
        str(tmp_path / "cfg.yaml"),
        _LogStub(),
        {"skip_catalog_sync": False, "only_pending_timeout_sec": 0},
    )

    assert ok is True
    proc = _FakePopen.instances[-1]
    assert "SKIP_POSTGRES_CATALOG_SYNC" not in proc.env
    # 0 = без таймаута: wait() ждёт бесконечно.
    assert proc.wait_timeouts == [None]


def test_run_only_pending_nonzero_exit_is_failure(tmp_path: Path, monkeypatch) -> None:
    _patch_popen(monkeypatch, returncode=2)

    assert run_only_pending(str(tmp_path / "cfg.yaml"), _LogStub(), {}) is False


def test_run_only_pending_timeout_kills_process_group(tmp_path: Path, monkeypatch) -> None:
    _patch_popen(monkeypatch, timeout_on_wait=True)
    log = _LogStub()

    ok = run_only_pending(str(tmp_path / "cfg.yaml"), log, {"only_pending_timeout_sec": 5})

    assert ok is False
    proc = _FakePopen.instances[-1]
    # Зависание: сначала wait(timeout=5), затем добивающий wait(30) внутри kill-хелпера.
    assert proc.wait_timeouts[0] == 5
    assert proc.killed is True
    assert "превысил таймаут 5s" in log.text()
