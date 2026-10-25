"""США/Autotrader: срезы SRP и контроль покрытия (глубина, курсор, total).

Эти тесты фиксируют поведение, из-за отсутствия которого каталог США
«срезался»: национальная выдача упирается в потолок глубины, курсор застревал
на последней странице, а расхождение «собрали / выдача показывает» нигде
не считалось.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import pytest

from scraper_pipeline.autotrader import browser_ingest as bi
from scraper_pipeline.autotrader.browser_ingest import (
    _cfg_from_config,
    _walk_segment,
    build_segments,
    split_segment,
)
from scraper_pipeline.autotrader.runtime_stats import AutotraderStats


def _srp_html(ids: List[str], total: int, next_url: Optional[str] = None) -> str:
    links = [{"rel": "next", "href": next_url}] if next_url else []
    nd = {
        "buildId": "test",
        "props": {
            "pageProps": {
                "__eggsState": {
                    "inventory": {str(i): {"id": str(i)} for i in ids},
                    "srp_results": {"activeResults": list(ids), "count": total},
                    "srp_srpPaginationLinks": {"links": links},
                }
            }
        },
    }
    return (
        "<html><body><script id=\"__NEXT_DATA__\" type=\"application/json\">"
        f"{json.dumps(nd)}</script></body></html>"
    )


class _FakeCheckpoint:
    def __init__(self) -> None:
        self.offsets: Dict[str, int] = {}
        self.state: Dict[str, str] = {}
        self.pending = 0

    async def get_last_offset(self, key: str) -> int:
        return int(self.offsets.get(key, 0) or 0)

    async def set_last_offset(self, key: str, value: int) -> None:
        self.offsets[key] = int(value)

    async def get_state(self, key: str) -> Optional[str]:
        return self.state.get(key)

    async def set_state(self, key: str, value: str) -> None:
        self.state[key] = str(value)

    async def pending_count(self) -> int:
        return self.pending


class _FakeRuntime:
    def __init__(self, cfg: Any, checkpoint: Optional[_FakeCheckpoint] = None) -> None:
        self.cfg = cfg
        self.lg = logging.getLogger("test.autotrader")
        self.checkpoint = checkpoint
        self.stop = asyncio.Event()
        self.next_srp_url: Optional[str] = None
        self.st = AutotraderStats()
        self.srp_pages_total = 0
        self.seg_cfg: Dict[str, Any] = {}
        self.answers: List[Any] = []
        self.urls: List[str] = []

    async def bump(self, field: str, n: int = 1) -> None:
        if n == 0:
            return
        setattr(self.st, field, int(getattr(self.st, field, 0) or 0) + int(n))

    async def note_error(self, msg: str) -> None:
        self.st.errors.append(msg)

    async def saved(self) -> int:
        return int(self.st.saved)

    async def recover_access(self, slot_key: str = "srp", *, failed_proxy: Any = None) -> None:
        return None


class _FakeTransport:
    """Отдаёт заранее заготовленные ответы (HTML или исключение) по порядку."""

    def __init__(self, rt: Any, kind: str, *, use_srp_page: bool = False, slot_key: str = "srp") -> None:
        self.rt = rt
        self.kind = kind
        self.page = "fake"
        self.slot_key = slot_key

    async def fetch(self, url: str) -> Optional[str]:
        self.rt.urls.append(url)
        if not self.rt.answers:
            raise RuntimeError("нет ответа")
        item = self.rt.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        return None


def _cfg(_at: Optional[Dict[str, Any]] = None, **seg: Any) -> Any:
    at: Dict[str, Any] = {
        "srp_retries": 1,
        "srp_stall_pages_limit": 1,
        "list_page_delay_min": 0,
        "list_page_delay_max": 0,
        "segmentation": seg,
    }
    if _at:
        at.update(_at)
    return _cfg_from_config({"autotrader": at})


# ------------------------------------------------------------------ срезы


def test_build_segments_price_x_year_product() -> None:
    segs = build_segments(
        {
            "enabled": True,
            "strategy": "price_x_year",
            "price_segments": [[0, 20000], [20000, 40000]],
            "year_segments": [[2010, 2019], [2020, 2026]],
        }
    )
    assert [s["name"] for s in segs] == [
        "p0-20000_y2010-2019",
        "p0-20000_y2020-2026",
        "p20000-40000_y2010-2019",
        "p20000-40000_y2020-2026",
    ]
    assert segs[0]["query"] == {
        "minPrice": 0,
        "maxPrice": 20000,
        "startYear": 2010,
        "endYear": 2019,
    }


def test_build_segments_make_price_and_cap() -> None:
    segs = build_segments(
        {
            "enabled": True,
            "strategy": "make_price",
            "make_codes": ["bmw", "HYUND"],
            "price_segments": ["0-25000", {"min": 25000, "max": 100000}],
            "max_segments": 3,
        }
    )
    assert len(segs) == 3
    assert segs[0]["name"] == "bmw_p0-25000"
    assert segs[1]["query"]["makeCode"] == "BMW"
    assert segs[1]["query"]["minPrice"] == 25000


def test_build_segments_disabled_or_missing_axis() -> None:
    assert build_segments({"enabled": False}) == []
    assert build_segments({"enabled": True, "strategy": "price_x_year", "price_segments": [["0", "1"]]}) == []


def test_split_segment_price_then_year_then_hopeless() -> None:
    kids = split_segment({"name": "p0-100", "query": {"minPrice": 0, "maxPrice": 100}, "depth": 0})
    assert [k["name"] for k in kids] == ["p0-50", "p50-100"]
    assert all(k["depth"] == 1 for k in kids)

    kids = split_segment(
        {"name": "y2010-2019", "query": {"startYear": 2010, "endYear": 2019}, "depth": 1}
    )
    assert [(k["query"]["startYear"], k["query"]["endYear"]) for k in kids] == [
        (2010, 2014),
        (2015, 2019),
    ]

    assert split_segment({"name": "bmw", "query": {"makeCode": "BMW"}, "depth": 0}) == []


# ------------------------------------------------- покрытие: обход среза


async def test_walk_segment_collects_ids_and_resets_cursor(monkeypatch) -> None:
    cfg = _cfg(depth_cap_pages=10, reset_cursor_on_complete=True)
    cp = _FakeCheckpoint()
    rt = _FakeRuntime(cfg, cp)
    rt.answers = [
        _srp_html([str(i) for i in range(1, 26)], total=50, next_url="/cars-for-sale/all-cars?page=2"),
        _srp_html([str(i) for i in range(26, 51)], total=50, next_url=None),
        _srp_html([], total=50),
    ]
    monkeypatch.setattr(bi, "_Transport", _FakeTransport)

    queued: List[List[Any]] = []

    async def emit(items: List[Any]) -> int:
        queued.append(items)
        return len(items)

    res = await _walk_segment(
        rt,
        emit,
        {"name": "p0-20000", "query": {"minPrice": 0, "maxPrice": 20000}, "depth": 0},
    )

    assert res["pages"] == 2  # страницы с id (пустая страница закрывает выдачу)
    assert res["ids"] == 50
    assert res["total"] == 50
    assert res["coverage_pct"] == 100.0
    assert res["truncated"] is False
    assert [len(batch) for batch in queued] == [25, 25]
    # срез закрыт → курсор сбрасывается на 1, чтобы следующий проход начал с головы
    assert cp.offsets["srp:p0-20000"] == 0
    assert cp.state["srp_ids:p0-20000"] == "50"
    assert rt.st.list_pages_ok == 3
    assert "minPrice=0" in rt.urls[0] and "page=1" in rt.urls[0]


async def test_walk_segment_detects_depth_limit(monkeypatch) -> None:
    cfg = _cfg(depth_cap_pages=0, depth_limit_streak=2, reset_cursor_on_complete=True)
    cp = _FakeCheckpoint()
    rt = _FakeRuntime(cfg, cp)
    rt.answers = [
        _srp_html([str(i) for i in range(1, 26)], total=3468733, next_url="/x?page=2"),
        # Глубокая страница: __NEXT_DATA__ есть, но inventory/count нет — это и есть
        # «потолок глубины» Autotrader, а не сетевой сбой.
        _srp_html([], total=None),
        _srp_html([], total=None),
    ]
    monkeypatch.setattr(bi, "_Transport", _FakeTransport)

    async def emit(items: List[Any]) -> int:
        return len(items)

    res = await _walk_segment(rt, emit, {"name": "all", "query": {}, "depth": 0})

    assert res["truncated"] is True
    assert res["pages"] == 3  # 1 нормальная + 2 страницы-потолка
    assert res["ids"] == 25
    assert res["coverage_pct"] < 1.0
    assert cp.state.get("srp_truncated:all") == "1"
    assert rt.st.list_pages_fail == 2


async def test_walk_segment_pre_splits_oversized_slice(monkeypatch) -> None:
    cfg = _cfg(depth_cap_pages=2, adaptive_split=True, max_split_depth=3)
    rt = _FakeRuntime(cfg, _FakeCheckpoint())
    rt.answers = [_srp_html([str(i) for i in range(1, 26)], total=10000)]
    monkeypatch.setattr(bi, "_Transport", _FakeTransport)

    async def emit(items: List[Any]) -> int:
        raise AssertionError("переполненный срез не должен ставить id в очередь")

    res = await _walk_segment(
        rt, emit, {"name": "p0-50000", "query": {"minPrice": 0, "maxPrice": 50000}, "depth": 0}
    )

    assert res["split"] is True
    assert res["total"] == 10000
    assert rt.st.ids_queued == 0


async def test_walk_segment_quota_keeps_cursor(monkeypatch) -> None:
    cfg = _cfg(depth_cap_pages=1000, segment_max_pages=1, reset_cursor_on_complete=True)
    cp = _FakeCheckpoint()
    rt = _FakeRuntime(cfg, cp)
    rt.answers = [_srp_html([str(i) for i in range(1, 26)], total=5000, next_url="/x?page=2")]
    monkeypatch.setattr(bi, "_Transport", _FakeTransport)

    async def emit(items: List[Any]) -> int:
        return len(items)

    res = await _walk_segment(
        rt, emit, {"name": "p0-5000", "query": {"minPrice": 0, "maxPrice": 5000}, "depth": 0}
    )

    assert res["quota"] is True
    # при квоте курсор НЕ сбрасывается — следующий проход идёт глубже
    assert cp.offsets["srp:p0-5000"] == 2



WAF_PAGE = (
    "<html><head><title>Autotrader - page unavailable</title></head><body>"
    "We're sorry for any inconvenience, but the site is currently unavailable. "
    "Incident Number: 18.5cce0b17.1792913180.5869fec"
    "</body></html>"
)


def test_is_autotrader_waf_block() -> None:
    from scraper_pipeline.autotrader.client import is_autotrader_waf_block

    assert is_autotrader_waf_block(WAF_PAGE) is True
    assert is_autotrader_waf_block(_srp_html(["1"], total=10)) is False
    assert is_autotrader_waf_block("") is False


async def test_walk_segment_aborts_on_waf_block_and_keeps_cursor(monkeypatch) -> None:
    cfg = _cfg(_at={"block_abort_after": 2, "srp_retries": 5}, depth_cap_pages=0, reset_cursor_on_complete=True)
    cp = _FakeCheckpoint()
    rt = _FakeRuntime(cfg, cp)
    rt.answers = [WAF_PAGE, WAF_PAGE]
    monkeypatch.setattr(bi, "_Transport", _FakeTransport)

    async def emit(items: List[Any]) -> int:
        raise AssertionError("при WAF-блоке в очередь ничего не попадает")

    res = await _walk_segment(
        rt, emit, {"name": "p0-8000", "query": {"minPrice": 0, "maxPrice": 8000}, "depth": 0}
    )

    assert res["blocked"] is True
    assert rt.st.srp_waf_blocks == 2
    assert rt.stop.is_set()  # проход закрыт, а не бесконечный recover
    # одна попытка на страницу, а не srp_retries=5: блок не лечится ретраями
    assert len(rt.urls) == 2
    # курсор не сброшен: данных не было, следующий прогон продолжит с того же места
    assert "srp:p0-8000" not in cp.offsets


class _FakePage:
    """Минимум от Playwright-страницы: отдаёт заранее заданный HTML."""

    def __init__(self, html: str) -> None:
        self._html = html

    async def goto(self, url: str, **kwargs: Any) -> None:
        return None

    async def wait_for_function(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("нет ни __NEXT_DATA__, ни 'unavailable'")

    async def wait_for_timeout(self, ms: int) -> None:
        return None

    async def content(self) -> str:
        return self._html


async def test_browser_goto_classifies_waf_block() -> None:
    """`page unavailable` из браузера обязан стать `_WafBlockError`, а не challenge."""
    pool = bi._BrowserPool(
        None,
        None,
        None,
        None,
        _cfg(),
        logging.getLogger("test.autotrader"),
        proxy_url=None,
        user_agent="ua",
        impersonate="chrome",
    )
    with pytest.raises(bi._WafBlockError):
        await pool.goto(_FakePage(WAF_PAGE), "https://www.autotrader.com/cars-for-sale/all-cars")

    with pytest.raises(RuntimeError) as exc:
        await pool.goto(_FakePage("<html><body>пусто</body></html>"), "https://www.autotrader.com/x")
    assert not isinstance(exc.value, bi._WafBlockError)


async def test_http_gate_classifies_waf_block() -> None:
    """HTTP-путь тоже обязан отдавать `_WafBlockError` наверх (иначе 5 ретраев впустую)."""
    gate = bi._HttpGate({}, _cfg(), logging.getLogger("test.autotrader"))
    gate.enabled = True

    class _Client:
        async def fetch_html(self, url: str) -> str:
            return WAF_PAGE

    async def _ensure() -> Any:
        return _Client()

    gate._ensure = _ensure  # type: ignore[assignment]

    with pytest.raises(bi._WafBlockError):
        await gate.fetch("https://www.autotrader.com/cars-for-sale/all-cars")

    class _OkClient:
        async def fetch_html(self, url: str) -> str:
            return _srp_html(["1"], total=1)

    async def _ensure_ok() -> Any:
        return _OkClient()

    gate._ensure = _ensure_ok  # type: ignore[assignment]
    gate.fail_streak = 0
    assert await gate.fetch("https://www.autotrader.com/cars-for-sale/all-cars") is not None

    # Клиент может сам классифицировать блок (без ретраев и Chromium)
    from scraper_pipeline.autotrader.client import AutotraderWafBlock

    class _BlockingClient:
        async def fetch_html(self, url: str) -> str:
            raise AutotraderWafBlock("WAF block HTTP 200")

    async def _ensure_block() -> Any:
        return _BlockingClient()

    gate._ensure = _ensure_block  # type: ignore[assignment]
    with pytest.raises(bi._WafBlockError):
        await gate.fetch("https://www.autotrader.com/cars-for-sale/all-cars")


async def test_client_raises_waf_block_without_retries() -> None:
    """WAF-блок не должен тратить challenge_retries и refresh_session."""
    from scraper_pipeline.autotrader.client import (
        AsyncAutotraderClient,
        AutotraderWafBlock,
    )

    calls: List[str] = []

    class _Resp:
        status = 200
        error = None
        text = WAF_PAGE

    class _Tr:
        async def request(self, *args: Any, **kwargs: Any) -> Any:
            calls.append("req")
            return _Resp()

    client = AsyncAutotraderClient(
        {"autotrader": {}}, logging.getLogger("test.autotrader"), auto_bootstrap=False
    )
    client._opened = True
    client._transport = _Tr()  # type: ignore[assignment]

    with pytest.raises(AutotraderWafBlock):
        await client.fetch_html("https://www.autotrader.com/cars-for-sale/all-cars")
    assert len(calls) == 1  # без challenge_retries и без refresh_session

