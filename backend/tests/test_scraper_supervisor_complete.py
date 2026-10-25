"""Unit tests for supervisor COMPLETE / final-sync guards (importlib load)."""
from __future__ import annotations

import importlib.util
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

