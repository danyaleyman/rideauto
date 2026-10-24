"""Autotrader ingest (USA): двухфазный контур discovery → pending → detail.

Архитектура выровнена с Encar/Che168:

* **Фаза 1 (discovery, SRP).** Страницы листинга разбираются, id пишутся в
  ``scraper_pending_ids(scope=autotrader)``, курсор страницы — в чекпоинт
  (``get_last_offset("all")``). Очередь наполняется быстрее, чем её дренят
  detail-воркеры, поэтому detail-фаза не простаивает на сети SRP.
* **Фаза 2 (detail, VDP).** Воркеры дренят pending-очередь батчами:
  успешный VDP → ``mark_collected`` + save; транзиентный сбой → requeue
  (не более ``vdp_max_attempts`` прогонов на карточку); страница «снято с продажи»
  → ``mark_collected`` без ретраев.
* **Транспорт.** HTTP-first (``curl_cffi`` + cookies из Playwright bootstrap) с
  автоматическим откатом на Chromium. Пока Akamai пускает curl_cffi — работаем
  по HTTP с большой конкурентностью; при challenge переходим на браузер и
  переливаем свежие cookies обратно в HTTP-сессию.

``phase="all"`` — обе фазы в одном процессе; ``phase="list"`` — только наполнение
очереди; ``phase="detail"`` — только разбор очереди (для параллельного запуска
второго процесса, как у Che168/Encar).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urlencode

from scraper_pipeline.autotrader.client import (
    AsyncAutotraderClient,
    is_autotrader_challenge_html,
)
from scraper_pipeline.autotrader.parser import (
    car_id_for_listing,
    is_page_unavailable,
    normalize_listing,
    parse_srp_page,
    parse_vdp_page,
)
from scraper_pipeline.autotrader.runtime_stats import AutotraderStats
from scraper_pipeline.autotrader.session import (
    apply_session_bundle_to_autotrader_config,
    build_autotrader_proxy_pool,
    collect_autotrader_cookies,
    ensure_autotrader_session,
    save_cached_session,
)
from scraper_pipeline.checkpoint_pg import CheckpointAsync
from scraper_pipeline.common.proxy_pool import ProxyPool
from scraper_pipeline.encar.savers import CarSaver
from scraper_pipeline.pg_dsn_resolve import resolve_scraper_postgres_dsn
from scraper_pipeline.resilience.browser_profile import resolve_browser_profile
from scraper_pipeline.resilience.session_bundle import SessionBundle
from scraper_pipeline.resilience.session_provider import playwright_proxy_config

log = logging.getLogger(__name__)

# Ключ курсора SRP в scraper_checkpoint_state (get_last_offset/set_last_offset).
SRP_CURSOR_KEY = "all"
# Общий car_type для pending-очереди Autotrader.
AT_CAR_TYPE = "autotrader"

_PHASE_ALIASES = {
    "all": "all",
    "both": "all",
    "full": "all",
    "list": "list",
    "srp": "list",
    "discovery": "list",
    "detail": "detail",
    "vdp": "detail",
    "pending": "detail",
    "only-pending": "detail",
    "only_pending": "detail",
}


@dataclass
class _AtCfg:
    """Разобранная конфигурация Autotrader (без словарного шума в каждой функции)."""

    phase: str = "all"
    base: str = "https://www.autotrader.com"
    start_url: str = ""
    start_page: int = 1
    max_pages: int = 0
    max_cars: int = 0
    detail_conc: int = 8
    pending_batch: int = 200
    pending_idle_sec: float = 45.0
    vdp_retries: int = 3
    vdp_max_attempts: int = 3
    srp_retries: int = 4
    srp_stall_pages: int = 4
    fetch_vdp: bool = True
    require_vdp: bool = True
    stub_on_give_up: bool = False
    http_first: bool = True
    http_fail_disable: int = 3
    http_wall: float = 45.0
    http_max_revives: int = 5
    timeout_ms: int = 120000
    wait_ms: int = 4000
    headless: bool = True
    delay_min: float = 0.6
    delay_max: float = 1.8
    vdp_delay_min: float = 0.05
    vdp_delay_max: float = 0.35
    save_batch: int = 64
    save_flush_sec: float = 2.0
    num_records: int = 0
    use_checkpoint: bool = True
    resume_cursor: bool = True
    # Пауза SRP, пока pending не просядет (0 = не паузить). Как у Encar.
    list_pause_when_pending_above: int = 0
    # Sticky Chromium на воркера (свой egress/прокси); false = один общий контекст.
    sticky_browser_slots: bool = True

    @property
    def do_list(self) -> bool:
        return self.phase in ("all", "list")

    @property
    def do_detail(self) -> bool:
        return self.phase in ("all", "detail")

    def srp_url(self, page: int, next_url: Optional[str] = None) -> str:
        """URL SRP: приоритет — ссылка пагинации со страницы, иначе сборка запроса."""
        if next_url:
            if next_url.startswith("http"):
                return next_url
            if next_url.startswith("/"):
                return f"{self.base}{next_url}"
            return f"{self.base}/{next_url}"
        if page <= 1:
            return self.start_url or f"{self.base}/cars-for-sale/all-cars"
        q: Dict[str, Any] = {}
        if self.num_records > 0:
            q["numRecords"] = self.num_records
        q["page"] = int(page)
        return f"{self.base}/cars-for-sale/all-cars?{urlencode(q)}"

    def vdp_url(self, listing_id: str) -> str:
        return f"{self.base}/cars-for-sale/vehicle/{listing_id}"


def _cfg_from_config(
    config: dict,
    *,
    phase: Any = None,
    only_pending: bool = False,
    start_page: Optional[int] = None,
    max_pages: Optional[int] = None,
    max_cars: Optional[int] = None,
) -> _AtCfg:
    at = config.get("autotrader") or {}
    http = config.get("http") or {}

    def _int(*vals: Any, default: int = 0) -> int:
        for v in vals:
            if v in (None, ""):
                continue
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
        return default

    def _float(*vals: Any, default: float = 0.0) -> float:
        for v in vals:
            if v in (None, ""):
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
        return default

    def _bool(key: str, default: bool) -> bool:
        if key not in at:
            return default
        raw = at.get(key)
        if raw is None:
            return default
        return str(raw).strip().lower() not in ("0", "false", "no", "off", "")

    base = str(at.get("base_url") or "https://www.autotrader.com").rstrip("/")
    cfg = _AtCfg(
        phase=_normalize_phase(
            phase if phase is not None else at.get("phase"), only_pending=only_pending
        ),
        base=base,
        start_url=str(at.get("bootstrap_start_url") or f"{base}/cars-for-sale/all-cars").strip(),
        start_page=max(1, start_page if start_page is not None else _int(at.get("start_page"), default=1)),
        max_pages=max_pages if max_pages is not None else _int(at.get("max_pages"), config.get("max_pages")),
        max_cars=max_cars if max_cars is not None else _int(at.get("max_cars"), config.get("max_cars")),
        detail_conc=max(1, _int(at.get("detail_concurrency"), http.get("concurrency"), default=2)),
        pending_batch=max(1, _int(at.get("pending_batch_size"), default=200)),
        pending_idle_sec=max(3.0, _float(at.get("pending_idle_sec"), default=45.0)),
        vdp_retries=max(1, _int(at.get("vdp_retries"), default=3)),
        vdp_max_attempts=max(1, _int(at.get("vdp_max_attempts"), default=3)),
        srp_retries=max(1, _int(at.get("srp_retries"), default=4)),
        srp_stall_pages=max(1, _int(at.get("srp_stall_pages_limit"), default=4)),
        fetch_vdp=_bool("fetch_vdp", True),
        require_vdp=_bool("require_vdp", True),
        http_first=_bool("http_first", True),
        http_fail_disable=max(1, _int(at.get("http_fail_disable"), default=3)),
        http_wall=max(5.0, _float(at.get("http_timeout_sec"), http.get("timeout_total"), default=45.0)),
        http_max_revives=max(0, _int(at.get("http_max_revives"), default=5)),
        timeout_ms=max(15000, _int(at.get("playwright_timeout_ms"), default=120000)),
        wait_ms=max(0, _int(at.get("playwright_post_load_wait_ms"), default=4000)),
        headless=at.get("playwright_headless", True) is not False,
        delay_min=_float(http.get("list_page_delay_min"), at.get("list_page_delay_min"), default=0.6),
        delay_max=_float(http.get("list_page_delay_max"), at.get("list_page_delay_max"), default=1.8),
        vdp_delay_min=_float(at.get("vdp_delay_min"), default=0.05),
        vdp_delay_max=_float(at.get("vdp_delay_max"), default=0.35),
        save_batch=max(1, _int(at.get("save_batch_size"), default=64)),
        save_flush_sec=max(0.0, _float(at.get("save_flush_sec"), default=2.0)),
        num_records=max(0, _int(at.get("srp_num_records"), default=0)),
        use_checkpoint=_bool("use_checkpoint", True),
        resume_cursor=_bool("resume_cursor", True),
        list_pause_when_pending_above=max(
            0, _int(at.get("list_pause_when_pending_above"), default=0)
        ),
        sticky_browser_slots=_bool("sticky_browser_slots", True),
    )
    # require_vdp=true означает «SRP-стаб не сохраняем», поэтому stub_on_vdp_fail
    # имеет силу только когда require_vdp выключен.
    cfg.stub_on_give_up = _bool("stub_on_vdp_fail", False) and not cfg.require_vdp
    # Akamai: >3 параллельных Chromium-контекста обычно сыпет challenge.
    # Явный force оставляет ops-эксперименты возможными.
    if cfg.detail_conc > 3 and not _bool("detail_concurrency_force", False):
        cfg.detail_conc = 3
    return cfg



def _normalize_phase(raw: Any, *, only_pending: bool = False) -> str:
    if only_pending:
        return "detail"
    key = str(raw or "all").strip().lower()
    return _PHASE_ALIASES.get(key, "all")


def run_autotrader_browser_ingest(
    saver: CarSaver,
    config: dict,
    *,
    phase: Any = None,
    only_pending: bool = False,
    start_page: Optional[int] = None,
    max_pages: Optional[int] = None,
    max_cars: Optional[int] = None,
    logger: Optional[logging.Logger] = None,
    stats: Optional[AutotraderStats] = None,
) -> AutotraderStats:
    """Sync entrypoint; runs the async pool (safe outside an existing event loop)."""
    kwargs: Dict[str, Any] = dict(
        phase=phase,
        only_pending=only_pending,
        start_page=start_page,
        max_pages=max_pages,
        max_cars=max_cars,
        logger=logger,
        stats=stats,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run_autotrader_browser_ingest_async(saver, config, **kwargs))
    # В этом потоке уже есть loop — уходим в отдельный поток со своим loop.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(lambda: asyncio.run(_run_autotrader_browser_ingest_async(saver, config, **kwargs)))
        return fut.result()


# --------------------------------------------------------------------- сохранение


class _SaveBuffer:
    """Буфер сохранений с ``bulk_save`` (одна транзакция на пачку, как у Encar)."""

    def __init__(
        self,
        saver: CarSaver,
        checkpoint: Optional[CheckpointAsync],
        *,
        batch: int,
        flush_sec: float,
        lg: logging.Logger,
    ) -> None:
        self._saver = saver
        self._checkpoint = checkpoint
        self._batch = max(1, int(batch))
        self._flush_sec = max(0.0, float(flush_sec))
        self._lg = lg
        self._rows: List[Tuple[dict, str]] = []
        self._last = time.perf_counter()
        self._lock = asyncio.Lock()

    async def add(self, car: dict, car_id: str) -> int:
        async with self._lock:
            self._rows.append((car, car_id))
            return await self._flush_locked(force=False)

    async def flush(self, force: bool = False) -> int:
        async with self._lock:
            return await self._flush_locked(force=force)

    async def _flush_locked(self, *, force: bool) -> int:
        if not self._rows:
            return 0
        now = time.perf_counter()
        if not force and len(self._rows) < self._batch and (now - self._last) < self._flush_sec:
            return 0
        rows = self._rows
        self._rows = []
        saved = 0
        try:
            if len(rows) == 1:
                await self._save_one(*rows[0])
                saved = 1
            else:
                written = int(await self._saver.bulk_save(list(rows), batch_size=self._batch) or 0)
                saved = min(max(written, 0), len(rows))
                if saved < len(rows):  # частичный bulk_save — добиваем поштучно
                    for car, cid in rows[saved:]:
                        await self._save_one(car, cid)
                        saved += 1
            if self._checkpoint is not None:
                for _car, cid in rows:
                    try:
                        await self._checkpoint.mark_collected(cid)
                    except Exception as e:  # маркер не критичен: карточка уже в БД
                        self._lg.warning("mark_collected %s failed: %s", cid, e)
        finally:
            self._last = time.perf_counter()
        return saved

    async def _save_one(self, car: dict, car_id: str) -> None:
        save_sync = getattr(self._saver, "_save_sync", None)
        if callable(save_sync):
            await asyncio.to_thread(save_sync, car, car_id)
        else:
            await self._saver.save_car(car, car_id)



# ----------------------------------------------------------------------- браузер


class _BrowserPool:
    """Один Chromium-контекст: SRP-страница + страницы для detail-воркеров."""

    def __init__(
        self,
        browser: Any,
        context: Any,
        srp_page: Any,
        pw: Any,
        cfg: _AtCfg,
        lg: logging.Logger,
        *,
        proxy_url: Optional[str],
        user_agent: str,
        impersonate: str,
    ) -> None:
        self._browser = browser
        self._context = context
        self._pw = pw
        self.srp_page = srp_page
        self._cfg = cfg
        self._lg = lg
        self.proxy_url = proxy_url
        self.user_agent = user_agent
        self.impersonate = impersonate

    async def new_page(self) -> Any:
        return await self._context.new_page()

    async def goto(self, page: Any, url: str) -> str:
        """Навигация + ожидание ``__NEXT_DATA__``/«unavailable»; иначе исключение."""
        await page.goto(url, wait_until="domcontentloaded", timeout=self._cfg.timeout_ms)
        try:
            await page.wait_for_function(
                "() => !!document.getElementById('__NEXT_DATA__') "
                "|| /unavailable|no longer available|not available/i.test(document.body.innerText || '')",
                timeout=min(self._cfg.timeout_ms, 45000),
            )
        except Exception:
            pass
        if self._cfg.wait_ms > 0:
            await page.wait_for_timeout(self._cfg.wait_ms)
        html = (await page.content()) or ""
        if not html:
            raise RuntimeError(f"browser: пустой HTML для {url}")
        if is_autotrader_challenge_html(html) and "__NEXT_DATA__" not in html:
            raise RuntimeError(f"browser: Akamai challenge для {url} (len={len(html)})")
        if "__NEXT_DATA__" not in html and not is_page_unavailable(html):
            raise RuntimeError(f"browser: нет __NEXT_DATA__ для {url} (len={len(html)})")
        return html

    async def cookies(self) -> Dict[str, str]:
        return collect_autotrader_cookies(await self._context.cookies())

    async def close(self) -> None:
        for closer in (
            getattr(self._context, "close", None),
            getattr(self._browser, "close", None),
            getattr(self._pw, "stop", None),
        ):
            if callable(closer):
                try:
                    await closer()
                except Exception:
                    pass


async def _launch_pool(
    cfg: _AtCfg,
    config: dict,
    lg: logging.Logger,
    *,
    proxy_pool: Optional[ProxyPool] = None,
    avoid_proxy: Optional[str] = None,
) -> _BrowserPool:
    """Поднять Chromium-контекст на живом прокси (с учётом quarantine)."""
    from playwright.async_api import async_playwright

    profile = resolve_browser_profile(config)
    pool = proxy_pool or build_autotrader_proxy_pool(config)
    # Кандидаты: сначала live из ProxyPool (round-robin), затем None (direct).
    ordered: List[Optional[str]] = []
    seen: Set[Optional[str]] = set()
    urls = pool.all()
    if urls:
        # Перебираем до len(urls) уникальных next_url, избегая avoid_proxy первым.
        for _ in range(max(1, len(urls) * 2)):
            cand = pool.next_url()
            if cand is None or cand in seen:
                continue
            if avoid_proxy and cand == avoid_proxy and len(urls) > 1:
                continue
            seen.add(cand)
            ordered.append(cand)
            if len(ordered) >= len(urls):
                break
        if avoid_proxy and avoid_proxy in urls and avoid_proxy not in seen:
            ordered.append(avoid_proxy)
    else:
        ordered = [None]
    last_err: Optional[BaseException] = None
    for proxy_url in ordered:
        pw_proxy = playwright_proxy_config(proxy_url)
        launch_kw: Dict[str, Any] = {"headless": cfg.headless}
        if pw_proxy:
            launch_kw["proxy"] = pw_proxy
        try:
            pw = await async_playwright().start()
        except Exception as e:  # Playwright не установлен / не стартует
            raise RuntimeError(f"Playwright не запустился: {e}") from e
        try:
            browser = await pw.chromium.launch(**launch_kw)
        except Exception as e:
            last_err = e
            lg.warning("Autotrader: chromium launch proxy=%s failed: %s", bool(proxy_url), e)
            if proxy_url and pool.mark_failure(proxy_url):
                lg.warning(
                    "Autotrader proxy quarantine: %s (launch fail); quarantined=%s/%s",
                    proxy_url.split("@")[-1] if proxy_url else "?",
                    pool.quarantined_now(),
                    len(pool.all()),
                )
            try:
                await pw.stop()
            except Exception:
                pass
            continue
        context = await browser.new_context(
            user_agent=profile.user_agent,
            locale="en-US",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "sec-ch-ua": profile.sec_ch_ua,
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
        )
        srp_page = await context.new_page()
        if proxy_url:
            pool.mark_success(proxy_url)
        lg.info(
            "Autotrader: браузерный контекст поднят proxy=%s headless=%s",
            bool(proxy_url),
            cfg.headless,
        )
        return _BrowserPool(
            browser,
            context,
            srp_page,
            pw,
            cfg,
            lg,
            proxy_url=proxy_url,
            user_agent=profile.user_agent,
            impersonate=profile.impersonate,
        )
    raise RuntimeError(f"Autotrader: chromium не поднялся ни на одном прокси. Last error: {last_err}")


class _BrowserFleet:
    """Sticky Chromium-слоты: SRP + по одному egress на detail-воркера.

    При challenge/падении ротируется только слот, а не весь пул — остальные
    воркеры продолжают на своих sticky-прокси (см. рекомендацию stable USA speedup).
    """

    def __init__(
        self,
        cfg: _AtCfg,
        config: dict,
        lg: logging.Logger,
        proxy_pool: ProxyPool,
    ) -> None:
        self._cfg = cfg
        self._config = config
        self._lg = lg
        self.proxy_pool = proxy_pool
        self._slots: Dict[str, _BrowserPool] = {}
        self._lock = asyncio.Lock()

    def _key(self, slot_key: str) -> str:
        if not self._cfg.sticky_browser_slots:
            return "shared"
        return slot_key or "srp"

    async def get(self, slot_key: str = "srp") -> _BrowserPool:
        key = self._key(slot_key)
        async with self._lock:
            cur = self._slots.get(key)
            if cur is not None:
                return cur
            pool = await _launch_pool(self._cfg, self._config, self._lg, proxy_pool=self.proxy_pool)
            self._slots[key] = pool
            self._lg.info(
                "Autotrader fleet: slot=%s proxy=%s slots=%s",
                key,
                bool(pool.proxy_url),
                len(self._slots),
            )
            return pool

    async def rotate(self, slot_key: str, *, failed_proxy: Optional[str] = None) -> _BrowserPool:
        key = self._key(slot_key)
        async with self._lock:
            old = self._slots.pop(key, None)
            if failed_proxy and self.proxy_pool.mark_failure(failed_proxy):
                self._lg.warning(
                    "Autotrader proxy quarantine: %s (browser fail); quarantined=%s/%s",
                    failed_proxy.split("@")[-1],
                    self.proxy_pool.quarantined_now(),
                    len(self.proxy_pool.all()),
                )
            if old is not None:
                self._lg.info("Autotrader fleet: rotate slot=%s", key)
                try:
                    await old.close()
                except Exception:
                    pass
            pool = await _launch_pool(
                self._cfg,
                self._config,
                self._lg,
                proxy_pool=self.proxy_pool,
                avoid_proxy=failed_proxy,
            )
            self._slots[key] = pool
            return pool

    async def close_all(self) -> None:
        async with self._lock:
            slots = list(self._slots.values())
            self._slots.clear()
        for pool in slots:
            try:
                await pool.close()
            except Exception:
                pass



# ------------------------------------------------------------------------- HTTP


class _HttpGate:
    """HTTP (curl_cffi) доступ: сам выключается после серии challenge, умеет оживать."""

    def __init__(self, config: dict, cfg: _AtCfg, lg: logging.Logger) -> None:
        self._config = config
        self._cfg = cfg
        self._lg = lg
        self._client: Optional[AsyncAutotraderClient] = None
        self._lock = asyncio.Lock()
        self.enabled = bool(cfg.http_first)
        self.fail_streak = 0
        self.revives = 0
        self.on_disable: Optional[Callable[[], Awaitable[None]]] = None

    async def _ensure(self) -> AsyncAutotraderClient:
        if self._client is None:
            client = AsyncAutotraderClient(self._config, self._lg, auto_bootstrap=False)
            await client.open()
            self._client = client
        return self._client

    async def fetch(self, url: str) -> Optional[str]:
        """HTML или None (выключен / challenge / ошибка). Исключений не бросает."""
        if not self.enabled:
            return None
        async with self._lock:
            if not self.enabled:
                return None
            try:
                client = await self._ensure()
                html = await asyncio.wait_for(client.fetch_html(url), timeout=self._cfg.http_wall)
            except Exception as e:
                self.fail_streak += 1
                self._lg.info(
                    "Autotrader HTTP miss (%s/%s): %s",
                    self.fail_streak,
                    self._cfg.http_fail_disable,
                    e,
                )
                if self.fail_streak >= self._cfg.http_fail_disable:
                    self.enabled = False
                    if self.on_disable is not None:
                        await self.on_disable()
                return None
        if is_autotrader_challenge_html(html):
            self.fail_streak += 1
            if self.fail_streak >= self._cfg.http_fail_disable:
                self.enabled = False
                if self.on_disable is not None:
                    await self.on_disable()
            return None
        if "__NEXT_DATA__" not in html and not is_page_unavailable(html):
            self.fail_streak += 1
            return None
        self.fail_streak = 0
        return html

    def reload_session(self) -> None:
        """Подхватить свежие cookies/UA из config (после браузерного bootstrap)."""
        if self._client is not None:
            self._client.reload_session()

    def revive(self) -> bool:
        """После свежих cookies из браузера попробовать HTTP снова (ограниченно)."""
        if self.enabled or self._client is None:
            return False
        if self.revives >= self._cfg.http_max_revives:
            return False
        self.revives += 1
        self.fail_streak = 0
        self.enabled = True
        self._lg.info("Autotrader HTTP: возрождаем curl_cffi (%s/%s)", self.revives, self._cfg.http_max_revives)
        return True

    async def hard_reset(self) -> None:
        """Полный сброс HTTP-клиента после force-bootstrap (новый egress/cookies)."""
        await self.close()
        self.fail_streak = 0
        self.revives = 0
        self.enabled = bool(self._cfg.http_first)

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass




# ---------------------------------------------------------------------- runtime


class _Runtime:
    """Общее состояние прогона: транспорт, пул браузера, чекпоинт, статистика."""

    def __init__(
        self,
        cfg: _AtCfg,
        config: dict,
        st: AutotraderStats,
        lg: logging.Logger,
        checkpoint: Optional[CheckpointAsync],
    ) -> None:
        self.cfg = cfg
        self.config = config
        self.st = st
        self.lg = lg
        self.checkpoint = checkpoint
        self.http = _HttpGate(config, cfg, lg)
        self.http.on_disable = self._on_http_disabled
        self.proxy_pool = build_autotrader_proxy_pool(config)
        self.fleet = _BrowserFleet(cfg, config, lg, self.proxy_pool)
        self.stats_lock = asyncio.Lock()
        self.stop = asyncio.Event()
        self.next_srp_url: Optional[str] = None
        self._last_cookie_sync = 0.0

    async def bump(self, field: str, n: int = 1) -> None:
        if n == 0:
            return
        async with self.stats_lock:
            setattr(self.st, field, int(getattr(self.st, field, 0) or 0) + int(n))

    async def bump_path(self, path: str) -> None:
        async with self.stats_lock:
            paths = self.st.extract_paths
            paths[path] = int(paths.get(path, 0) or 0) + 1

    async def note_error(self, msg: str) -> None:
        async with self.stats_lock:
            if len(self.st.errors) < 1000:
                self.st.errors.append(msg)

    async def saved(self) -> int:
        async with self.stats_lock:
            return int(self.st.saved)

    async def _on_http_disabled(self) -> None:
        await self.bump("http_disabled_after")

    async def ensure_pool(self, slot_key: str = "srp") -> _BrowserPool:
        return await self.fleet.get(slot_key)

    async def reset_pool(self, slot_key: str = "srp", *, failed_proxy: Optional[str] = None) -> None:
        """Сбросить один sticky-слот (не весь флот) и поднять на другом прокси."""
        try:
            await self.fleet.rotate(slot_key, failed_proxy=failed_proxy)
        except Exception as e:
            self.lg.warning("Autotrader: rotate slot=%s failed: %s", slot_key, e)

    async def recover_access(self, slot_key: str = "srp", *, failed_proxy: Optional[str] = None) -> None:
        """Жёсткое восстановление после серии Akamai: wipe session + новый bootstrap + rotate."""
        from scraper_pipeline.autotrader.session import (
            apply_session_bundle_to_autotrader_config,
            ensure_autotrader_session,
            session_cache_path,
        )

        path = session_cache_path(self.config)
        if path is not None and path.is_file():
            try:
                path.unlink()
                self.lg.info("Autotrader: session cache wiped (%s)", path)
            except OSError as e:
                self.lg.warning("Autotrader: session wipe failed: %s", e)
        # Сначала гасим все Chromium-слоты — иначе recover копит процессы до OOM.
        try:
            await self.fleet.close_all()
        except Exception as e:
            self.lg.warning("Autotrader: fleet close_all failed: %s", e)
        await self.http.hard_reset()
        try:
            bundle = await asyncio.to_thread(
                ensure_autotrader_session, self.config, self.lg, True
            )
            apply_session_bundle_to_autotrader_config(self.config, bundle, self.lg)
        except Exception as e:
            self.lg.warning("Autotrader: force bootstrap failed: %s", e)
        # Один новый SRP-слот (не ротируем впустую до первого fetch).
        try:
            await self.ensure_pool(slot_key)
        except Exception as e:
            self.lg.warning("Autotrader: pool after recover failed: %s", e)
        try:
            self.http.reload_session()
        except Exception:
            pass

    async def sync_cookies(self, pool: _BrowserPool, *, force: bool = False) -> None:
        """Свежие cookies из браузера → кэш сессии + HTTP-клиент (троттлинг 60 с)."""
        now = time.time()
        if not force and (now - self._last_cookie_sync) < 60.0:
            return
        self._last_cookie_sync = now
        try:
            cookies = await pool.cookies()
        except Exception as e:
            self.lg.warning("Autotrader: cookies из контекста не прочитались: %s", e)
            return
        if not cookies:
            return
        if pool.proxy_url:
            self.proxy_pool.mark_success(pool.proxy_url)
        bundle = SessionBundle(
            source="autotrader",
            cookies=cookies,
            proxy_url=pool.proxy_url,
            user_agent=pool.user_agent,
            impersonate_id=pool.impersonate,
            obtained_at=now,
            meta={
                "fetch_mode": "playwright",
                "detail_workers": self.cfg.detail_conc,
                "proxy_snapshot": self.proxy_pool.snapshot(),
            },
        )
        try:
            save_cached_session(self.config, bundle, self.lg)
            apply_session_bundle_to_autotrader_config(self.config, bundle, self.lg)
            self.http.reload_session()
            self.http.revive()
        except Exception as e:
            self.lg.warning("Autotrader: не удалось применить cookies: %s", e)

    async def close(self) -> None:
        await self.fleet.close_all()
        await self.http.close()


class _Transport:
    """HTTP-first с ленивой браузерной страницей (своя на поток).

    ``HTTP → (challenge/ошибка) → Chromium`` — первый удачный браузерный ответ
    переливает cookies в HTTP-сессию, чтобы вернуться на быстрый путь.
    Sticky-слот: ``slot_key`` (``srp`` / ``w0``…) — отдельный egress на воркера.
    """

    def __init__(
        self,
        rt: _Runtime,
        kind: str,
        *,
        use_srp_page: bool = False,
        slot_key: str = "srp",
    ) -> None:
        self.rt = rt
        self.kind = kind
        self.use_srp_page = use_srp_page
        self.slot_key = slot_key
        self.page: Any = None

    async def fetch(self, url: str) -> Optional[str]:
        html = await self.rt.http.fetch(url)
        if html is not None:
            await self.rt.bump(f"{self.kind}_via_http")
            return html
        pool = await self.rt.ensure_pool(self.slot_key)
        if self.page is None:
            self.page = pool.srp_page if self.use_srp_page else await pool.new_page()
        try:
            html = await pool.goto(self.page, url)
        except Exception as e:
            self.rt.lg.warning("Autotrader browser %s failed %s: %s", self.kind, url, e)
            failed = pool.proxy_url
            await self.rt.reset_pool(self.slot_key, failed_proxy=failed)
            self.page = None
            raise
        await self.rt.bump(f"{self.kind}_via_browser")
        await self.rt.sync_cookies(pool)
        return html

    async def close(self) -> None:
        if self.page is not None and not self.use_srp_page:
            try:
                await self.page.close()
            except Exception:
                pass
        self.page = None



# ---------------------------------------------------------------- фаза 1: SRP



async def _discovery_phase(
    rt: _Runtime,
    emit: Optional[Callable[[List[Tuple[str, str, Optional[dict]]]], Awaitable[int]]] = None,
) -> None:
    """Фаза 1: SRP-страницы → очередь.

    ``emit`` кладёт очередную страницу в pending (Postgres) или в память;
    возвращает число реально новых карточек (нужно для детектора стабилизации).
    """
    cfg, lg, cp = rt.cfg, rt.lg, rt.checkpoint
    tr = _Transport(rt, "srp", use_srp_page=True)
    page = cfg.start_page
    if cfg.resume_cursor:
        try:
            cursor = int(await cp.get_last_offset(SRP_CURSOR_KEY) or 0)
        except Exception:
            cursor = 0
        if cursor > page:
            page = cursor
            lg.info("Autotrader discovery: продолжаем с page=%s (курсор чекпоинта)", page)
    pages_done = 0
    stale_full = 0
    prev_ids: Set[str] = set()
    pause_above = int(cfg.list_pause_when_pending_above or 0)
    try:
        while not rt.stop.is_set():
            if cfg.max_pages > 0 and pages_done >= cfg.max_pages:
                lg.info("Autotrader discovery: достигнут max_pages=%s", cfg.max_pages)
                break
            if cfg.max_cars > 0 and await rt.saved() >= cfg.max_cars:
                lg.info("Autotrader discovery: max_cars=%s достигнут", cfg.max_cars)
                break

            if pause_above > 0 and cp is not None:
                try:
                    pend_now = int(await cp.pending_count() or 0)
                except Exception:
                    pend_now = 0
                pause_rounds = 0
                while pend_now >= pause_above and not rt.stop.is_set():
                    if pause_rounds == 0 or pause_rounds % 15 == 0:
                        lg.info(
                            "Autotrader list pause: pending=%s >= %s — ждём detail",
                            pend_now,
                            pause_above,
                        )
                    pause_rounds += 1
                    await asyncio.sleep(20 + random.uniform(0.0, 3.0))
                    try:
                        pend_now = int(await cp.pending_count() or 0)
                    except Exception:
                        break
                if pause_rounds:
                    lg.info(
                        "Autotrader list resume: pending=%s после %s пауз",
                        pend_now,
                        pause_rounds,
                    )

            url = cfg.srp_url(page, rt.next_srp_url)
            parsed: Optional[Dict[str, Any]] = None
            last_err: Optional[BaseException] = None
            for attempt in range(1, cfg.srp_retries + 1):
                if rt.stop.is_set():
                    break
                try:
                    html = await tr.fetch(url)
                    if not html:
                        raise RuntimeError("пустой HTML")
                    if is_autotrader_challenge_html(html):
                        raise RuntimeError(
                            f"Akamai challenge HTML (len={len(html)})"
                        )
                    candidate = parse_srp_page(html)
                    if not candidate.get("ok"):
                        raise RuntimeError("SRP parse failed (нет __NEXT_DATA__/inventory)")
                    parsed = candidate
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    lg.warning("SRP page=%s попытка %s/%s: %s", page, attempt, cfg.srp_retries, e)
                    # Transport.fetch уже ротирует sticky-слот при browser fail —
                    # здесь НЕ поднимаем второй Chromium (иначе OOM-шторм на DE-4).
                    tr.page = None
                    await asyncio.sleep(random.uniform(cfg.delay_min * 2, cfg.delay_max * 3))
            if parsed is None or last_err is not None:
                await rt.bump("list_pages_fail")
                await rt.note_error(f"srp page={page}: {last_err}")
                stale_full += 1
                lg.error(
                    "SRP page=%s не удалась за %s попыток — hold+recover (fail_streak %s/%s)",
                    page,
                    cfg.srp_retries,
                    stale_full,
                    cfg.srp_stall_pages,
                )
                rt.next_srp_url = None
                tr.page = None
                # Не двигаем page/cursor при challenge. Cool-down + force bootstrap.
                cool = min(180.0, 20.0 + float(stale_full) * 15.0)
                lg.info(
                    "Autotrader discovery: cool-down %.0fs then recover (stay on page=%s)",
                    cool,
                    page,
                )
                await asyncio.sleep(cool)
                await rt.recover_access(tr.slot_key)
                if stale_full >= cfg.srp_stall_pages:
                    # Не выходим из discovery — сбрасываем streak после recover,
                    # иначе supervisor-рестарт крутит тот же мёртвый session cache.
                    lg.warning(
                        "Autotrader discovery: fail_streak=%s — streak reset after recover, stay on page=%s",
                        stale_full,
                        page,
                    )
                    stale_full = 0
                continue

            await rt.bump("list_pages_ok")
            ids = [str(x) for x in (parsed.get("active_ids") or [])]
            inventory = parsed.get("inventory") or {}
            nxt = parsed.get("next_page_url")
            rt.next_srp_url = str(nxt) if nxt else None
            lg.info(
                "SRP page=%s ids=%s total=%s inventory=%s next=%s",
                page,
                len(ids),
                parsed.get("total_count"),
                len(inventory),
                bool(rt.next_srp_url),
            )
            if not ids:
                stale_full += 1
                lg.info(
                    "SRP page=%s без id — stall %s/%s",
                    page,
                    stale_full,
                    cfg.srp_stall_pages,
                )
                if stale_full >= cfg.srp_stall_pages:
                    lg.info("SRP: каталог исчерпан (пустые страницы подряд)")
                    break
                rt.next_srp_url = None
                page += 1
                pages_done += 1
                try:
                    await cp.set_last_offset(SRP_CURSOR_KEY, page)
                except Exception:
                    pass
                continue

            await rt.bump("listings_seen", len(ids))
            items: List[Tuple[str, str, Optional[dict]]] = []
            for lid in ids:
                items.append((car_id_for_listing(lid), AT_CAR_TYPE, _srp_stub_payload(lid, inventory.get(lid))))
            added = 0
            if emit is not None:
                try:
                    added = int(await emit(items) or 0)
                except Exception as e:
                    await rt.note_error(f"srp page={page} emit: {e}")
                    lg.warning("SRP page=%s: постановка в очередь не прошла: %s", page, e)
            await rt.bump("ids_queued", added)

            same_as_prev = bool(prev_ids) and set(ids) == prev_ids
            prev_ids = set(ids)
            if added == 0 and (same_as_prev or len(ids) >= 20):
                stale_full += 1
                lg.info(
                    "SRP page=%s: новых id 0 (стабильных страниц %s/%s)",
                    page,
                    stale_full,
                    cfg.srp_stall_pages,
                )
                if stale_full >= cfg.srp_stall_pages:
                    lg.info("Autotrader discovery: каталог стабилизировался — стоп")
                    break
            else:
                stale_full = 0

            pages_done += 1
            page += 1
            if cp is not None:
                try:
                    await cp.set_last_offset(SRP_CURSOR_KEY, page)
                except Exception as e:
                    lg.debug("set_last_offset(%s) не прошёл: %s", page, e)
            await asyncio.sleep(random.uniform(cfg.delay_min, cfg.delay_max))
    finally:
        await tr.close()


# ------------------------------------------------------------------ обработка карточки

_ATTEMPTS_KEY = "_at_attempts"


def _attempts_of(payload: Optional[dict]) -> int:
    if isinstance(payload, dict):
        try:
            return max(0, int(payload.get(_ATTEMPTS_KEY) or 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _srp_stub_payload(listing_id: str, payload: Optional[dict]) -> Dict[str, Any]:
    """Минимальная полезная нагрузка для карточки из SRP-очереди."""
    out: Dict[str, Any] = dict(payload) if isinstance(payload, dict) else {}
    out.setdefault("listingId", listing_id)
    out.setdefault("id", listing_id)
    return out


def _retry_payload(listing_id: str, payload: Optional[dict], attempts: int) -> Dict[str, Any]:
    out = _srp_stub_payload(listing_id, payload)
    out[_ATTEMPTS_KEY] = max(0, int(attempts))
    return out


def _listing_id_from_cid(cid: str) -> str:
    prefix = "autotrader-"
    s = str(cid or "").strip()
    return s[len(prefix):] if s.startswith(prefix) else s


async def _safe_mark_collected(cp: Optional[CheckpointAsync], cid: str, lg: logging.Logger) -> None:
    if cp is None:
        return
    try:
        await cp.mark_collected(cid)
    except Exception as e:
        lg.warning("mark_collected %s не прошёл: %s", cid, e)


async def _process_card(
    rt: _Runtime,
    buf: _SaveBuffer,
    wid: int,
    lid: str,
    car_type: str,
    payload: Optional[dict],
    requeue: Callable[[str, str, Optional[dict]], Awaitable[None]],
) -> str:
    """Обработать одну карточку из очереди. Возвращает исход для логов/тестов."""
    cfg, lg, cp = rt.cfg, rt.lg, rt.checkpoint
    cid = car_id_for_listing(lid)

    if cp is not None:
        try:
            if await cp.is_collected(cid):
                await rt.bump("skipped")
                return "collected"
        except Exception as e:
            lg.debug("is_collected(%s) не прошёл: %s", cid, e)

    if cfg.max_cars > 0 and await rt.saved() >= cfg.max_cars:
        if cp is not None:
            await requeue(cid, car_type, _retry_payload(lid, payload, _attempts_of(payload)))
        return "deferred"

    card = _srp_stub_payload(lid, payload)
    attempts = _attempts_of(payload)
    await rt.bump("listings_seen")
    listing: Optional[dict] = card
    depth = "srp"
    last_err: Optional[BaseException] = None

    if cfg.fetch_vdp:
        for _attempt in range(1, cfg.vdp_retries + 1):
            if rt.stop.is_set():
                break
            html: Optional[str] = None
            tr = _Transport(rt, "vdp", slot_key=f"w{wid}")
            try:
                html = await tr.fetch(cfg.vdp_url(lid))
            except Exception as e:
                last_err = e
            finally:
                await tr.close()
            if html:
                if is_page_unavailable(html):
                    await rt.bump("gone")
                    await _safe_mark_collected(cp, cid, lg)
                    lg.info("autotrader %s: карточка снята с продажи — ретраи не нужны", cid)
                    return "gone"
                parsed = parse_vdp_page(html, listing_id=lid)
                if parsed.get("ok") and isinstance(parsed.get("listing"), dict):
                    listing = parsed["listing"]
                    depth = "vdp"
                    last_err = None
                    await rt.bump("details_ok")
                    await rt.bump_path(str(parsed.get("extract_path") or "unknown"))
                    if not parsed.get("has_next_data"):
                        await rt.bump_path("no_next_data")
                    break
                last_err = RuntimeError("VDP распарсился пусто")
            await asyncio.sleep(random.uniform(cfg.vdp_delay_min, cfg.vdp_delay_max))
        if depth != "vdp":
            await rt.bump("details_fail")
            await rt.note_error(f"vdp {lid}: {last_err}")
            if cp is not None and (attempts + 1) < cfg.vdp_max_attempts:
                await requeue(cid, car_type, _retry_payload(lid, payload, attempts + 1))
                await rt.bump("requeued")
                lg.info(
                    "autotrader %s: VDP не удался (%s) — вернули в очередь, попытка %s/%s",
                    cid,
                    last_err,
                    attempts + 2,
                    cfg.vdp_max_attempts,
                )
                return "requeued"
            if not cfg.stub_on_give_up:
                await rt.bump("gave_up")
                await _safe_mark_collected(cp, cid, lg)
                lg.info(
                    "autotrader %s: VDP не удался %s прогон(ов) — исключаем из очереди (%s)",
                    cid,
                    cfg.vdp_max_attempts,
                    last_err,
                )
                return "gave_up"
            await rt.bump("stub_saved")
            lg.info("autotrader %s: сохраняем SRP-стаб без VDP", cid)

    if not isinstance(listing, dict):
        await rt.bump("skipped")
        return "skip"
    try:
        car = normalize_listing(listing, listing_id=lid, depth=depth)
    except Exception as e:
        await rt.bump("details_fail")
        await rt.note_error(f"normalize {lid}: {e}")
        lg.warning("normalize %s не удался: %s", lid, e)
        return "skip"
    try:
        await buf.add(car, cid)
    except Exception as e:
        await rt.note_error(f"save {lid}: {e}")
        lg.exception("Autotrader save failed %s", lid)
        if cp is not None:
            await requeue(cid, car_type, _retry_payload(lid, payload, attempts))
        return "save_fail"
    await rt.bump("saved")
    lg.info(
        "saved %s depth=%s images=%s features=%s worker=%s total=%s",
        cid,
        depth,
        len(car.get("images") or []),
        len(car.get("features") or []),
        wid,
        await rt.saved(),
    )
    if cfg.max_cars > 0 and await rt.saved() >= cfg.max_cars:
        rt.stop.set()
    return "saved" if depth == "vdp" else "stub"




# --------------------------------------------------------------- фаза 2: detail


async def _worker_loop(
    rt: _Runtime,
    buf: _SaveBuffer,
    wid: int,
    q: "asyncio.Queue[Any]",
    requeue: Callable[[str, str, Optional[dict]], Awaitable[None]],
) -> None:
    while True:
        item = await q.get()
        try:
            if item is None:
                return
            lid, car_type, payload = item
            await _process_card(rt, buf, wid, lid, car_type or AT_CAR_TYPE, payload, requeue)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            rt.lg.exception("Autotrader worker %s: %s", wid, e)
            await rt.note_error(f"worker {wid}: {e}")
        finally:
            q.task_done()


async def _detail_phase(
    rt: _Runtime,
    saver: CarSaver,
    *,
    discovery_task: Optional["asyncio.Task[None]"] = None,
) -> None:
    """Фаза 2: дренаж pending-очереди Postgres батчами на несколько воркеров."""
    cfg, lg, cp = rt.cfg, rt.lg, rt.checkpoint
    if cp is None:
        raise RuntimeError("detail-фаза требует Postgres-чекпоинт (pending-очередь)")
    buf = _SaveBuffer(saver, cp, batch=cfg.save_batch, flush_sec=cfg.save_flush_sec, lg=lg)
    q: "asyncio.Queue[Any]" = asyncio.Queue(maxsize=max(16, cfg.detail_conc * 4))

    async def requeue(cid: str, car_type: str, payload: Optional[dict]) -> None:
        try:
            ij = json.dumps(payload, ensure_ascii=False) if payload else None
            await cp.add_pending(cid, car_type or AT_CAR_TYPE, ij)
        except Exception as e:
            lg.warning("requeue %s не прошёл: %s", cid, e)

    workers = [asyncio.create_task(_worker_loop(rt, buf, i, q, requeue)) for i in range(cfg.detail_conc)]
    idle_rounds = 0
    idle_limit = max(3, int(cfg.pending_idle_sec))
    batches = 0
    try:
        while not rt.stop.is_set():
            try:
                batch = await cp.pop_pending_batch(cfg.pending_batch)
            except Exception as e:
                lg.error("pop_pending_batch не прошёл: %s", e)
                await asyncio.sleep(2.0)
                continue
            if not batch:
                idle_rounds += 1
                discovery_alive = discovery_task is not None and not discovery_task.done()
                # phase=all: ждём, пока жив discovery. phase=detail (SPLIT): list — другой
                # процесс, поэтому тоже ждём idle_limit сек, а не выходим на первом пустом батче.
                if discovery_task is not None and discovery_task.done() and idle_rounds >= 3:
                    lg.info("Autotrader detail: discovery finished, pending empty — stop")
                    break
                if idle_rounds >= idle_limit:
                    if discovery_alive:
                        lg.warning(
                            "Autotrader detail: очередь пуста %ss при работающем discovery — выходим",
                            idle_rounds,
                        )
                    else:
                        lg.info(
                            "Autotrader detail: pending пуст после %ss ожидания — стоп",
                            idle_rounds,
                        )
                    break
                await asyncio.sleep(1.0)
                continue
            idle_rounds = 0
            for cid, car_type, payload in batch:
                await q.put((_listing_id_from_cid(cid), car_type or AT_CAR_TYPE, payload))
            await q.join()
            batches += 1
            if cfg.max_cars > 0 and await rt.saved() >= cfg.max_cars:
                lg.info("Autotrader detail: max_cars=%s достигнут", cfg.max_cars)
                rt.stop.set()
            if batches % 5 == 0:
                try:
                    left = int(await cp.pending_count() or 0)
                except Exception:
                    left = -1
                lg.info(
                    "Autotrader detail: пачек=%s saved=%s pending=%s",
                    batches,
                    await rt.saved(),
                    left,
                )
    finally:
        for _ in workers:
            await q.put(None)
        await asyncio.gather(*workers, return_exceptions=True)
        try:
            await buf.flush(force=True)
        except Exception as e:
            lg.warning("flush остатка не удался: %s", e)
        try:
            rt.st.pending_left = int(await cp.pending_count() or 0)
        except Exception:
            pass


# ------------------------------------------------ режим без Postgres (в памяти)


async def _combined_phase(rt: _Runtime, saver: CarSaver) -> None:
    """Discovery + detail в одном процессе с очередью в памяти (нет DSN/чекпоинта)."""
    cfg, lg = rt.cfg, rt.lg
    buf = _SaveBuffer(saver, None, batch=cfg.save_batch, flush_sec=cfg.save_flush_sec, lg=lg)
    q: "asyncio.Queue[Any]" = asyncio.Queue(maxsize=max(16, cfg.detail_conc * 4))
    queued_ids: Set[str] = set()
    tries: Dict[str, int] = {}

    async def requeue(cid: str, car_type: str, payload: Optional[dict]) -> None:
        if rt.stop.is_set():
            return
        attempts = _attempts_of(payload)
        if attempts >= cfg.vdp_max_attempts:
            return
        await q.put((_listing_id_from_cid(cid), car_type or AT_CAR_TYPE, payload))

    async def emit(items: List[Tuple[str, str, Optional[dict]]]) -> int:
        added = 0
        for cid, car_type, payload in items:
            n = tries.get(cid, 0)
            if cid in queued_ids and n >= cfg.vdp_max_attempts:
                continue
            queued_ids.add(cid)
            tries[cid] = max(n, _attempts_of(payload))
            await q.put((_listing_id_from_cid(cid), car_type, payload))
            added += 1
        return added

    workers = [asyncio.create_task(_worker_loop(rt, buf, i, q, requeue)) for i in range(cfg.detail_conc)]
    try:
        await _discovery_phase(rt, emit)
        await q.join()  # requeue-элементы тоже проходят через join
        lg.info("Autotrader combined: очередь в памяти разобрана (saved=%s)", await rt.saved())
    finally:
        for _ in workers:
            await q.put(None)
        await asyncio.gather(*workers, return_exceptions=True)
        try:
            await buf.flush(force=True)
        except Exception as e:
            lg.warning("flush остатка не удался: %s", e)


def _checkpoint_emitter(rt: _Runtime) -> Callable[[List[Tuple[str, str, Optional[dict]]]], Awaitable[int]]:
    """emit для pending-очереди Postgres (фаза list / all с чекпоинтом)."""

    async def emit(items: List[Tuple[str, str, Optional[dict]]]) -> int:
        cp = rt.checkpoint
        if cp is None:
            return 0
        return int(await cp.add_pending_batch(items) or 0)

    return emit




# ---------------------------------------------------------------------- запуск


async def _run_autotrader_browser_ingest_async(
    saver: CarSaver,
    config: dict,
    *,
    phase: Any = None,
    only_pending: bool = False,
    start_page: Optional[int] = None,
    max_pages: Optional[int] = None,
    max_cars: Optional[int] = None,
    logger: Optional[logging.Logger] = None,
    stats: Optional[AutotraderStats] = None,
) -> AutotraderStats:
    lg = logger or log
    st = stats or AutotraderStats()
    cfg = _cfg_from_config(
        config,
        phase=phase,
        only_pending=only_pending,
        start_page=start_page,
        max_pages=max_pages,
        max_cars=max_cars,
    )

    checkpoint: Optional[CheckpointAsync] = None
    dsn = str(resolve_scraper_postgres_dsn(config) or "").strip()
    if cfg.use_checkpoint and dsn:
        scope = str((config.get("checkpoint") or {}).get("scope") or "autotrader")
        checkpoint = CheckpointAsync(dsn, scope=scope)
        try:
            await checkpoint.connect()
        except Exception as e:
            lg.warning("Autotrader: чекпоинт недоступен (%s) — работаем без pending-очереди", e)
            checkpoint = None
    if checkpoint is None and cfg.phase in ("list", "detail"):
        raise RuntimeError(f"phase={cfg.phase} требует Postgres-чекпоинт (pending-очередь)")

    rt = _Runtime(cfg, config, st, lg, checkpoint)

    # Прогреваем HTTP-сессию из кэша cookies (быстрый путь без браузера).
    if cfg.http_first:
        try:
            bundle = await asyncio.to_thread(ensure_autotrader_session, config, lg)
            apply_session_bundle_to_autotrader_config(config, bundle, lg)
        except Exception as e:
            lg.warning("Autotrader: сессию из кэша/PW взять не удалось (%s) — стартуем с браузера", e)

    lg.info(
        "Autotrader ingest: phase=%s cars=%s pages=%s workers=%s pending_batch=%s "
        "http_first=%s sticky=%s pause_pending=%s proxies=%s checkpoint=%s",
        cfg.phase,
        cfg.max_cars or "inf",
        cfg.max_pages or "inf",
        cfg.detail_conc,
        cfg.pending_batch,
        cfg.http_first,
        cfg.sticky_browser_slots,
        cfg.list_pause_when_pending_above,
        rt.proxy_pool.snapshot(),
        bool(checkpoint),
    )
    t0 = time.monotonic()
    try:
        if cfg.phase == "list":
            await _discovery_phase(rt, _checkpoint_emitter(rt))
        elif cfg.phase == "detail":
            await _detail_phase(rt, saver)
        elif checkpoint is None:
            await _combined_phase(rt, saver)
        else:
            # Параллельно: discovery наполняет pending, detail его дренит.
            discovery_task = asyncio.create_task(_discovery_phase(rt, _checkpoint_emitter(rt)))
            detail_task = asyncio.create_task(_detail_phase(rt, saver, discovery_task=discovery_task))
            done, still_running = await asyncio.wait(
                {discovery_task, detail_task}, return_when=asyncio.FIRST_EXCEPTION
            )
            for task in done:
                exc = task.exception()
                if exc is not None:
                    lg.error("Autotrader: фаза упала: %s", exc)
                    await rt.note_error(f"phase: {exc}")
                    rt.stop.set()
            await asyncio.gather(*still_running, return_exceptions=True)
    finally:
        await rt.close()
        if checkpoint is not None:
            try:
                st.pending_left = int(await checkpoint.pending_count() or 0)
            except Exception:
                pass
            await checkpoint.close()
    done_label = "only-pending done" if cfg.phase == "detail" else "ingest done"
    lg.info(
        "Autotrader %s phase=%s за %.1f c: %s",
        done_label,
        cfg.phase,
        time.monotonic() - t0,
        st.as_dict(),
    )
    return st

