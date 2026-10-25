"""Unit tests for supervisor COMPLETE / final-sync guards (importlib load)."""
from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass, field
from pathlib import Path


def _load():
    import sys

    root = Path(__file__).resolve().parents[2]
    p = root / "deploy" / "scripts" / "rideauto_scraper_supervisor.py"
    name = "rideauto_scraper_supervisor"
    spec = importlib.util.spec_from_file_location(name, str(p))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # dataclasses on 3.12+ need the module registered before exec.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_market_ready_for_complete_requires_pg_rows_and_idle_queue():
    mod = _load()
    assert mod.market_ready_for_complete(pending=0, running=False, log_done=True, pg_count=10) is True
    assert mod.market_ready_for_complete(pending=0, running=False, log_done=True, pg_count=0) is False
    assert mod.market_ready_for_complete(pending=1, running=False, log_done=True, pg_count=10) is False
    assert mod.market_ready_for_complete(pending=0, running=True, log_done=True, pg_count=10) is False
    assert mod.market_ready_for_complete(pending=0, running=False, log_done=False, pg_count=10) is False


def test_complete_confirm_ticks():
    mod = _load()

    @dataclass
    class M:
        complete_ticks: int = 0

    m = M()
    assert mod.note_complete_tick(m, False, 2) is False
    assert m.complete_ticks == 0
    assert mod.note_complete_tick(m, True, 2) is False
    assert m.complete_ticks == 1
    assert mod.note_complete_tick(m, True, 2) is True
    assert m.complete_ticks == 2
    # break streak
    assert mod.note_complete_tick(m, False, 2) is False
    assert m.complete_ticks == 0


def test_load_complete_markers(tmp_path: Path):
    mod = _load()
    markets = [
        mod.Market(name="encar", pattern="x", log_glob="e*.log", start_cmd=["true"]),
        mod.Market(name="che168", pattern="y", log_glob="c*.log", start_cmd=["true"]),
    ]
    (tmp_path / "encar.complete").write_text("2026-10-10T00:00:00Z", encoding="utf-8")
    mod.load_complete_markers(markets, tmp_path)
    assert markets[0].complete is True
    assert markets[1].complete is False


def test_last_list_pass_waf_blocked(tmp_path: Path):
    """WAF-аборт распознаётся только по последнему проходу, а не по всей истории."""
    mod = _load()
    ok_line = (
        "2026-10-25 10:00:00,000 [INFO] autotrader_scraper: Autotrader ingest done "
        "phase=list за 300.0 c: {'list_pages_ok': 24, 'srp_waf_blocks': 0, 'saved': 300}"
    )
    waf_line = (
        "2026-10-25 11:51:22,715 [INFO] autotrader_scraper: Autotrader ingest done "
        "phase=list за 168.2 c: {'list_pages_ok': 0, 'srp_waf_blocks': 8, 'saved': 0}"
    )
    p = tmp_path / "autotrader_scraper.log"
    p.write_text(waf_line + "\n", encoding="utf-8")
    assert mod.last_list_pass_waf_blocked(p) is True
    # успешный проход после блока снимает признак
    p.write_text(waf_line + "\n" + ok_line + "\n", encoding="utf-8")
    assert mod.last_list_pass_waf_blocked(p) is False
    # WAF без нулевого list_pages_ok — это частичные блоки, проход не закрыт
    p.write_text(
        waf_line.replace("'list_pages_ok': 0", "'list_pages_ok': 3") + "\n", encoding="utf-8"
    )
    assert mod.last_list_pass_waf_blocked(p) is False
    # нет строки статистики list-прохода
    p.write_text("2026-10-25 11:00:00,000 [INFO] x: y\n", encoding="utf-8")
    assert mod.last_list_pass_waf_blocked(p) is False
    assert mod.last_list_pass_waf_blocked(None) is False


def test_next_scheduled_run(tmp_path: Path):
    """Вечный idle допустим только когда повторов не ждём."""
    mod = _load()
    at = mod.Market(name="autotrader", pattern="a", log_glob="a*.log", start_cmd=["true"])
    encar = mod.Market(name="encar", pattern="e", log_glob="e*.log", start_cmd=["true"])
    assert mod.next_scheduled_run([at, encar]) == 0.0
    at.next_run_ts = 1_000_000.0
    assert mod.next_scheduled_run([at, encar]) == 1_000_000.0
    # чужие рынки не участвуют (у них нет повторов)
    encar.next_run_ts = 5.0
    assert mod.next_scheduled_run([at, encar]) == 1_000_000.0


def test_waf_pause_marker_survives_restart(tmp_path: Path):
    """После WAF-блока пауза восстанавливается как AT_WAF_BACKOFF_SEC, а не сутки."""
    mod = _load()
    at = mod.Market(name="autotrader", pattern="a", log_glob="a*.log", start_cmd=["true"])
    mod.write_markers(tmp_path, "autotrader", waf_pause=True)
    assert (tmp_path / "autotrader.complete").is_file()
    assert (tmp_path / "autotrader.waf_pause").is_file()

    mod.load_complete_markers([at], tmp_path)
    assert at.complete is True
    assert at.next_run_ts > 0
    expected = mod.marker_ts(tmp_path / "autotrader.waf_pause") + mod.AT_WAF_BACKOFF_SEC
    assert abs(at.next_run_ts - expected) < 2

    # нормальный COMPLETE снимает WAF-маркер (пауза = AT_RERUN_SEC)
    at2 = mod.Market(name="autotrader", pattern="a", log_glob="a*.log", start_cmd=["true"])
    mod.write_markers(tmp_path, "autotrader", waf_pause=False)
    assert not (tmp_path / "autotrader.waf_pause").is_file()
    mod.load_complete_markers([at2], tmp_path)
    assert abs(at2.next_run_ts - (mod.marker_ts(tmp_path / "autotrader.complete") + mod.AT_RERUN_SEC)) < 2


def test_waf_pause_marker_expires(tmp_path: Path):
    """Просроченная WAF-пауза удаляется, рынок снова в работе."""
    mod = _load()
    at = mod.Market(name="autotrader", pattern="a", log_glob="a*.log", start_cmd=["true"])
    old = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - mod.AT_WAF_BACKOFF_SEC - 60)
    )
    for name in ("autotrader.complete", "autotrader.waf_pause"):
        (tmp_path / name).write_text(old, encoding="utf-8")
    mod.load_complete_markers([at], tmp_path)
    # WAF-маркер истёк, но .complete ещё свежий относительно AT_RERUN_SEC
    assert not (tmp_path / "autotrader.waf_pause").is_file()
    assert at.complete is True


