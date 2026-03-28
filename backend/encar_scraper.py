"""
Production Encar.com scraper: async, resumable, configurable.
Collects list pages sequentially, fetches car details concurrently with rate limiting,
checkpoints state to SQLite, and stores results in SQLite or chunked JSON.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import random
import sqlite3
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import aiohttp
import yaml

# Reuse parsing logic from existing parser
from parser_full import EncarFullParser

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

def load_config(config_path: str = "scraper_config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    # Env override: SCRAPER_HTTP_CONCURRENCY=10 etc.
    for key, value in os.environ.items():
        if not key.startswith("SCRAPER_"):
            continue
        parts = key[8:].lower().split("_")  # SCRAPER_HTTP_CONCURRENCY -> http, concurrency
        if len(parts) < 2:
            continue
        section = parts[0]
        subkey = "_".join(parts[1:])
        if section not in config:
            config[section] = {}
        try:
            if isinstance(value, str) and value.isdigit():
                config[section][subkey] = int(value)
            elif value.lower() in ("true", "false"):
                config[section][subkey] = value.lower() == "true"
            else:
                config[section][subkey] = value
        except Exception:
            config[section][subkey] = value
    return config


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

def setup_logging(cfg: dict) -> logging.Logger:
    log_cfg = cfg.get("logging", {})
    level = getattr(logging, str(log_cfg.get("level", "INFO")).upper(), logging.INFO)
    fmt = log_cfg.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handlers: List[logging.Handler] = []
    if log_cfg.get("console", True):
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter(fmt))
        handlers.append(h)
    log_file = log_cfg.get("file")
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(fmt))
        handlers.append(fh)
    logging.basicConfig(level=level, format=fmt, handlers=handlers or [logging.StreamHandler()])
    return logging.getLogger("encar_scraper")


# -----------------------------------------------------------------------------
# Checkpoint (SQLite)
# -----------------------------------------------------------------------------

@dataclass
class Checkpoint:
    path: str
    max_pending: int
    conn: Optional[sqlite3.Connection] = field(default=None, repr=False)

    def connect(self) -> None:
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        assert self.conn
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS pending_ids (
                car_id TEXT NOT NULL,
                car_type TEXT NOT NULL,
                item_json TEXT,
                added_at REAL NOT NULL,
                PRIMARY KEY (car_id)
            );
            CREATE TABLE IF NOT EXISTS collected_ids (
                car_id TEXT PRIMARY KEY
            );
            CREATE INDEX IF NOT EXISTS idx_pending_added ON pending_ids(added_at);
        """)
        try:
            self.conn.execute("ALTER TABLE pending_ids ADD COLUMN item_json TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def get_state(self, key: str) -> Optional[str]:
        if not self.conn:
            return None
        row = self.conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_state(self, key: str, value: str) -> None:
        if not self.conn:
            return
        self.conn.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def get_last_offset(self, car_type: str) -> int:
        v = self.get_state(f"list_offset_{car_type}")
        return int(v) if v else 0

    def set_last_offset(self, car_type: str, offset: int) -> None:
        self.set_state(f"list_offset_{car_type}", str(offset))

    def add_pending(self, car_id: str, car_type: str, item_json: Optional[str] = None) -> bool:
        """Add to pending if not already collected. Returns True if added."""
        if not self.conn:
            return False
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO pending_ids (car_id, car_type, item_json, added_at) VALUES (?, ?, ?, ?)",
                (car_id, car_type, item_json, time.time()),
            )
            self.conn.commit()
            return self.conn.total_changes > 0
        except Exception:
            return False

    def add_pending_batch(self, items: List[Tuple[str, str, Optional[dict]]]) -> int:
        if not self.conn or not items:
            return 0
        now = time.time()
        added = 0
        for rec in items:
            car_id, car_type = rec[0], rec[1]
            item_json = json.dumps(rec[2], ensure_ascii=False) if len(rec) > 2 and rec[2] else None
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO pending_ids (car_id, car_type, item_json, added_at) VALUES (?, ?, ?, ?)",
                    (car_id, car_type, item_json, now),
                )
                if self.conn.total_changes > 0:
                    added += 1
            except Exception:
                pass
        self.conn.commit()
        return added

    def pop_pending_batch(self, limit: int) -> List[Tuple[str, str, Optional[dict]]]:
        if not self.conn:
            return []
        rows = self.conn.execute(
            "SELECT car_id, car_type, item_json FROM pending_ids ORDER BY added_at ASC LIMIT ?", (limit,)
        ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        self.conn.execute("DELETE FROM pending_ids WHERE car_id IN (" + ",".join("?" * len(ids)) + ")", ids)
        self.conn.commit()
        out = []
        for r in rows:
            item = json.loads(r[2]) if r[2] else None
            out.append((r[0], r[1], item))
        return out

    def pending_count(self) -> int:
        if not self.conn:
            return 0
        return self.conn.execute("SELECT COUNT(*) FROM pending_ids").fetchone()[0]

    def is_collected(self, car_id: str) -> bool:
        if not self.conn:
            return False
        return self.conn.execute("SELECT 1 FROM collected_ids WHERE car_id = ?", (car_id,)).fetchone() is not None

    def mark_collected(self, car_id: str) -> None:
        if not self.conn:
            return
        self.conn.execute("INSERT OR IGNORE INTO collected_ids (car_id) VALUES (?)", (car_id,))
        self.conn.commit()

    def remove_collected(self, car_id: str) -> None:
        if not self.conn:
            return
        self.conn.execute("DELETE FROM collected_ids WHERE car_id = ?", (car_id,))
        self.conn.commit()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None


# -----------------------------------------------------------------------------
# Storage backends
# -----------------------------------------------------------------------------

class StorageBase:
    def save_car(self, car: dict, car_id: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class SQLiteStorage(StorageBase):
    def __init__(self, path: str, store_raw: bool = False):
        self.path = path
        self.store_raw = store_raw
        self.conn: Optional[sqlite3.Connection] = None
        self._seq = 0

    def connect(self) -> None:
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id TEXT UNIQUE NOT NULL,
                data_json TEXT NOT NULL,
                raw_json TEXT,
                created_at TEXT
            )
        """)
        self.conn.commit()

    def save_car(self, car: dict, car_id: str) -> None:
        if not self.conn:
            return
        data_json = json.dumps(car, ensure_ascii=False)
        raw_json = json.dumps(car.get("_raw", {}), ensure_ascii=False) if self.store_raw and car.get("_raw") else None
        created = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO cars (car_id, data_json, raw_json, created_at) VALUES (?, ?, ?, ?)",
            (car_id, data_json, raw_json, created),
        )
        self.conn.commit()

    def get_car_ids_sample(self, limit: int = 500) -> List[str]:
        """Return up to `limit` car_id values (for sold check / refresh)."""
        if not self.conn:
            return []
        rows = self.conn.execute(
            "SELECT car_id FROM cars ORDER BY id LIMIT ?", (limit,)
        ).fetchall()
        return [r[0] for r in rows]

    def delete_car(self, car_id: str) -> None:
        if not self.conn:
            return
        self.conn.execute("DELETE FROM cars WHERE car_id = ?", (car_id,))
        self.conn.commit()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None


class ChunkedJSONStorage(StorageBase):
    def __init__(self, dir_path: str, cars_per_file: int = 1000, store_raw: bool = False):
        self.dir_path = Path(dir_path)
        self.cars_per_file = cars_per_file
        self.store_raw = store_raw
        self.current_chunk: List[dict] = []
        self.chunk_index = 0
        self.dir_path.mkdir(parents=True, exist_ok=True)
        self._find_next_chunk_index()

    def _find_next_chunk_index(self) -> None:
        existing = list(self.dir_path.glob("cars_*.json"))
        if not existing:
            self.chunk_index = 0
            return
        indices = []
        for p in existing:
            try:
                n = int(p.stem.split("_")[1])
                indices.append(n)
            except (IndexError, ValueError):
                pass
        self.chunk_index = max(indices, default=0)

    def save_car(self, car: dict, car_id: str) -> None:
        out = dict(car)
        if self.store_raw and car.get("_raw"):
            out["_raw"] = car["_raw"]
        self.current_chunk.append(out)
        if len(self.current_chunk) >= self.cars_per_file:
            self._flush_chunk()

    def _flush_chunk(self) -> None:
        if not self.current_chunk:
            return
        self.chunk_index += 1
        path = self.dir_path / f"cars_{self.chunk_index:05d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"result": self.current_chunk, "meta": {"chunk": self.chunk_index}}, f, ensure_ascii=False, indent=2)
        self.current_chunk = []

    def close(self) -> None:
        self._flush_chunk()


# -----------------------------------------------------------------------------
# Async HTTP client with retry, proxy, UA
# -----------------------------------------------------------------------------

class AsyncEncarClient:
    def __init__(
        self,
        config: dict,
        logger: logging.Logger,
    ):
        self.config = config
        self.log = logger
        http = config.get("http", {})
        self.list_url = "https://api.encar.com/search/car/list/general"
        self.base_api = "https://api.encar.com/v1/readside"
        self.conn_limit = http.get("conn_limit_per_host", 10)
        self.timeout = aiohttp.ClientTimeout(
            total=http.get("timeout_total", 30),
            connect=http.get("timeout_connect", 10),
        )
        self.jitter_min = http.get("request_jitter_min", 0.1)
        self.jitter_max = http.get("request_jitter_max", 0.5)
        retry = config.get("retry", {})
        self.max_attempts = retry.get("max_attempts", 5)
        self.backoff_base = retry.get("backoff_base", 1)
        self.backoff_max = retry.get("backoff_max", 60)
        self.retry_statuses = set(retry.get("retry_statuses", [429, 500, 502, 503, 504]))
        self.user_agents = config.get("user_agents", [])
        if not self.user_agents:
            self.user_agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"]
        proxy_cfg = config.get("proxy", {})
        self.proxies = proxy_cfg.get("urls", []) if proxy_cfg.get("enabled") else []
        self._session: Optional[aiohttp.ClientSession] = None
        self._proxy_index = 0
        self._ua_index = 0

    def _next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        self._proxy_index = (self._proxy_index + 1) % len(self.proxies)
        return self.proxies[self._proxy_index]

    def _next_ua(self) -> str:
        self._ua_index = (self._ua_index + 1) % len(self.user_agents)
        return self.user_agents[self._ua_index]

    async def _jitter(self) -> None:
        delay = random.uniform(self.jitter_min, self.jitter_max)
        await asyncio.sleep(delay)

    async def __aenter__(self) -> "AsyncEncarClient":
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=aiohttp.TCPConnector(limit_per_host=self.conn_limit),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        origin: str = "https://www.encar.com",
    ) -> Tuple[Optional[dict], int, Optional[str]]:
        """Returns (json_data, status_code, error_message)."""
        if not self._session:
            return None, 0, "no session"
        h = dict(headers or {})
        h.setdefault("User-Agent", self._next_ua())
        h.setdefault("Accept", "application/json, text/javascript, */*; q=0.01")
        h.setdefault("Accept-Language", "en-US,en;q=0.9")
        h.setdefault("Origin", origin)
        h.setdefault("Referer", origin + "/")
        last_error: Optional[str] = None
        for attempt in range(self.max_attempts):
            proxy = self._next_proxy()
            await self._jitter()
            try:
                async with self._session.request(
                    method, url, headers=h, params=params, proxy=proxy
                ) as resp:
                    retry_after = resp.headers.get("Retry-After")
                    if resp.status in self.retry_statuses:
                        last_error = f"status {resp.status}"
                        if retry_after and retry_after.isdigit():
                            await asyncio.sleep(min(int(retry_after), self.backoff_max))
                        else:
                            backoff = min(self.backoff_base * (2 ** attempt), self.backoff_max)
                            await asyncio.sleep(backoff)
                        continue
                    if resp.status != 200:
                        text = (await resp.text())[:500]
                        return None, resp.status, text
                    data = await resp.json()
                    return data, 200, None
            except asyncio.TimeoutError as e:
                last_error = str(e)
                await asyncio.sleep(min(self.backoff_base * (2 ** attempt), self.backoff_max))
            except aiohttp.ClientError as e:
                last_error = str(e)
                await asyncio.sleep(min(self.backoff_base * (2 ** attempt), self.backoff_max))
        return None, 0, last_error

    async def fetch_list_page(
        self, offset: int, limit: int, car_type: str
    ) -> Tuple[Optional[dict], int, Optional[str]]:
        car_type_flag = "N" if car_type == "for" else "Y"
        params = {
            "count": "true",
            "q": f"(And.Hidden.N._.CarType.{car_type_flag}.)",
            "sr": f"|ModifiedDate|{offset}|{limit}",
        }
        return await self._request(
            "GET",
            self.list_url,
            params=params,
            origin="https://www.encar.com",
        )

    async def fetch_vehicle_detail(self, car_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        url = f"{self.base_api}/vehicle/{car_id}"
        params = {"include": "ADVERTISEMENT,CATEGORY,CONDITION,CONTACT,MANAGE,OPTIONS,PHOTOS,SPEC,PARTNERSHIP,CENTER,VIEW"}
        return await self._request("GET", url, params=params, origin="https://fem.encar.com")

    async def fetch_record(self, car_id: str, plate_number: str) -> Tuple[Optional[dict], int, Optional[str]]:
        if not plate_number:
            return None, 0, "no plate"
        url = f"{self.base_api}/record/vehicle/{car_id}/open"
        params = {"vehicleNo": urllib.parse.quote(plate_number)}
        return await self._request("GET", url, params=params, origin="https://fem.encar.com")

    async def fetch_diagnosis(self, car_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        url = f"{self.base_api}/diagnosis/vehicle/{car_id}"
        return await self._request("GET", url, origin="https://fem.encar.com")

    async def fetch_inspection(self, car_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        url = f"{self.base_api}/inspection/vehicle/{car_id}"
        return await self._request("GET", url, origin="https://fem.encar.com")

    async def fetch_sellingpoint(self, car_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        url = f"{self.base_api}/diagnosis/vehicle/{car_id}/sellingpoint"
        return await self._request("GET", url, origin="https://fem.encar.com")

    async def fetch_user(self, user_id: str) -> Tuple[Optional[dict], int, Optional[str]]:
        if not user_id:
            return None, 0, "no user id"
        url = f"{self.base_api}/user/{user_id}"
        return await self._request("GET", url, origin="https://fem.encar.com")


# -----------------------------------------------------------------------------
# List producer (sequential)
# -----------------------------------------------------------------------------

async def list_producer(
    client: AsyncEncarClient,
    checkpoint: Checkpoint,
    config: dict,
    car_types: List[str],
    stats: dict,
    log: logging.Logger,
    max_cars: int = 0,
) -> None:
    http_cfg = config.get("http", {})
    page_size = http_cfg.get("list_page_size", 100)
    max_offset = http_cfg.get("max_list_offset", 10000)
    delay_min = http_cfg.get("list_page_delay_min", 0.5)
    delay_max = http_cfg.get("list_page_delay_max", 1.5)
    for car_type in car_types:
        if max_cars > 0 and stats.get("saved", 0) >= max_cars:
            log.info("List producer stopping: max_cars=%s reached", max_cars)
            break
        offset = checkpoint.get_last_offset(car_type)
        type_label = "import" if car_type == "for" else "domestic"
        list_fail_streak = 0
        while offset < max_offset:
            if max_cars > 0 and stats.get("saved", 0) >= max_cars:
                log.info("List producer stopping: max_cars=%s (уже в БД/сессии)", max_cars)
                break
            # Не копим десятки тысяч pending, если нужно всего max_cars карточек
            if max_cars > 0:
                pend = checkpoint.pending_count()
                if stats.get("saved", 0) + pend >= max_cars + 3 * page_size:
                    log.info(
                        "List producer stopping: достаточно очереди (saved=%s pending=%s max_cars=%s)",
                        stats.get("saved", 0), pend, max_cars,
                    )
                    break
            data, status, err = await client.fetch_list_page(offset, page_size, car_type)
            if status != 200 or not data:
                log.warning("List page failed car_type=%s offset=%s status=%s err=%s", car_type, offset, status, err)
                if status in (407, 429) or (status >= 500 and offset > 0):
                    list_fail_streak += 1
                    if list_fail_streak > 25:
                        log.error("List: too many failures at offset=%s, stopping list for %s", offset, car_type)
                        break
                    await asyncio.sleep(5 if status == 407 else 60)
                    continue
                break
            list_fail_streak = 0
            items = data.get("SearchResults") or []
            if not items:
                log.info("List exhausted car_type=%s at offset=%s", car_type, offset)
                break
            to_add = []
            for item in items:
                car_id = str(item.get("Id", ""))
                if not car_id:
                    continue
                if checkpoint.is_collected(car_id):
                    continue
                to_add.append((car_id, car_type, item))
            added = checkpoint.add_pending_batch(to_add)
            stats["list_pages"] += 1
            stats["ids_discovered"] += len(items)
            stats["ids_queued"] += added
            log.info("List car_type=%s offset=%s items=%s queued=%s", car_type, offset, len(items), added)
            checkpoint.set_last_offset(car_type, offset + page_size)
            offset += page_size
            await asyncio.sleep(random.uniform(delay_min, delay_max))
    log.info("List producer finished for car_types=%s", car_types)


# -----------------------------------------------------------------------------
# Detail worker: fetch one car, parse, save
# -----------------------------------------------------------------------------

def parse_one_car(
    parser: EncarFullParser,
    car_id: str,
    item: dict,
    detail: Optional[dict],
    diagnosis: Optional[dict],
    record: Optional[dict],
    inspection: Optional[dict],
    sellingpoint: Optional[dict],
    user_info: Optional[dict],
    _seq: int,
) -> Optional[dict]:
    try:
        inspection_structured = parser.parse_inspection(inspection, diagnosis) if (inspection or diagnosis) else {}
        photos = None
        if detail:
            photos = detail.get("photos") or []
        normalized = parser.normalize_car(
            car_id, item, detail, photos, diagnosis,
            inspection, sellingpoint, record, user_info,
            inspection_structured=inspection_structured,
        )
        # Используем стабильный Encar car_id для ссылок каталог → карточка (избегаем дубликатов id из-за гонки seq)
        normalized["id"] = car_id
        normalized["data"]["id"] = str(car_id)
        return normalized
    except Exception:
        return None


async def detail_worker(
    worker_id: int,
    client: AsyncEncarClient,
    checkpoint: Checkpoint,
    storage: StorageBase,
    parser: EncarFullParser,
    config: dict,
    queue: asyncio.Queue,
    stats: dict,
    log: logging.Logger,
    max_cars: int = 0,
    stats_lock: Optional[asyncio.Lock] = None,
) -> None:
    sem = asyncio.Semaphore(1)
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            if queue.empty():
                break
            continue
        if item is None:
            break
        if len(item) == 3:
            car_id, car_type, item_from_list = item
            if item_from_list is None:
                item_from_list = {}
        else:
            car_id, car_type = item[0], item[1]
            item_from_list = item[2] if len(item) > 2 else {}
        if not item_from_list:
            item_from_list = {"Id": car_id}
        if checkpoint.is_collected(car_id):
            queue.task_done()
            continue
        if max_cars > 0 and stats_lock is not None:
            async with stats_lock:
                if stats["saved"] >= max_cars:
                    queue.task_done()
                    continue
        async with sem:
            detail, d_status, _ = await client.fetch_vehicle_detail(car_id)
        if d_status != 200 or not detail:
            log.warning("Worker %s car_id=%s detail failed status=%s", worker_id, car_id, d_status)
            stats["detail_fail"] += 1
            queue.task_done()
            continue
        plate = detail.get("vehicleNo") if detail else None
        seller_id = None
        sep_item = detail.get("item")
        if isinstance(sep_item, list) and sep_item:
            sep_item = sep_item[0]
        if isinstance(sep_item, dict) and sep_item.get("Separation"):
            seller_id = (sep_item.get("Separation") or [None])[0]
        if not seller_id and item_from_list.get("Separation"):
            seller_id = (item_from_list.get("Separation") or [None])[0]
        has_diag = False
        if detail:
            adv = detail.get("advertisement") or {}
            if adv.get("hasUnderBodyPhoto"):
                has_diag = True
            for p in detail.get("photos") or []:
                if p.get("type") == "DIAG2":
                    has_diag = True
                    break
        tasks = []
        if plate:
            tasks.append(("record", client.fetch_record(car_id, plate)))
        if has_diag:
            tasks.append(("diagnosis", client.fetch_diagnosis(car_id)))
        tasks.append(("inspection", client.fetch_inspection(car_id)))
        tasks.append(("sellingpoint", client.fetch_sellingpoint(car_id)))
        if seller_id:
            tasks.append(("user", client.fetch_user(seller_id)))
        results = {}
        if tasks:
            done = await asyncio.gather(*[c for _, c in tasks], return_exceptions=True)
            for i, (name, _) in enumerate(tasks):
                if i >= len(done):
                    continue
                d = done[i]
                if isinstance(d, Exception):
                    log.debug("Worker %s car_id=%s %s: %s", worker_id, car_id, name, d)
                    results[name] = None
                else:
                    data, status, _ = d
                    results[name] = data if status == 200 else None
        record = results.get("record")
        diagnosis = results.get("diagnosis")
        inspection = results.get("inspection")
        if not inspection and detail:
            inspection = (detail.get("condition") or {}).get("inspection")
        sellingpoint = results.get("sellingpoint")
        user_info = results.get("user")
        car = parse_one_car(
            parser, car_id, item_from_list or {"Id": car_id}, detail, diagnosis, record,
            inspection, sellingpoint, user_info, stats["saved"] + 1,
        )
        if car:
            did_save = False
            if max_cars > 0 and stats_lock is not None:
                async with stats_lock:
                    if stats["saved"] < max_cars:
                        storage.save_car(car, car_id)
                        checkpoint.mark_collected(car_id)
                        stats["saved"] += 1
                        did_save = True
            else:
                storage.save_car(car, car_id)
                checkpoint.mark_collected(car_id)
                stats["saved"] += 1
                did_save = True
            if did_save and stats["saved"] % 100 == 0:
                log.info("Worker %s saved car_id=%s total=%s", worker_id, car_id, stats["saved"])
            if max_cars > 0 and not did_save:
                stats["parse_fail"] += 1
        else:
            stats["parse_fail"] += 1
        stats["processed"] += 1
        queue.task_done()


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

async def run_scraper(
    config_path: str = "scraper_config.yaml",
    max_cars_override: Optional[int] = None,
    only_pending: bool = False,
) -> None:
    config = load_config(config_path)
    log = setup_logging(config)
    log.info("Starting Encar scraper%s", " (only-pending)" if only_pending else "")
    checkpoint_cfg = config.get("checkpoint", {})
    cp_path = checkpoint_cfg.get("path", "scraper_checkpoint.db")
    max_pending = checkpoint_cfg.get("max_pending_ids", 500000)
    checkpoint = Checkpoint(path=cp_path, max_pending=max_pending)
    checkpoint.connect()
    storage_cfg = config.get("storage", {})
    backend = storage_cfg.get("backend", "sqlite")
    store_raw = storage_cfg.get("store_raw_responses", False)
    if backend == "sqlite":
        storage = SQLiteStorage(storage_cfg.get("sqlite", {}).get("path", "encar_cars.db"), store_raw=store_raw)
        if isinstance(storage, SQLiteStorage):
            storage.connect()
    else:
        cj = storage_cfg.get("chunked_json", {})
        storage = ChunkedJSONStorage(
            cj.get("dir", "output_chunks"),
            cj.get("cars_per_file", 1000),
            store_raw=store_raw,
        )
    car_types = config.get("car_types", ["for", "kor"])
    concurrency = config.get("http", {}).get("concurrency", 8)
    stats = {
        "list_pages": 0,
        "ids_discovered": 0,
        "ids_queued": 0,
        "processed": 0,
        "saved": 0,
        "detail_fail": 0,
        "parse_fail": 0,
    }
    # Уже сохранённые в SQLite машины учитываем в max_cars (иначе при рестарте list заливает тысячи pending).
    if backend == "sqlite" and isinstance(storage, SQLiteStorage) and storage.conn:
        try:
            row = storage.conn.execute("SELECT COUNT(*) FROM cars").fetchone()
            stats["saved"] = int(row[0] or 0)
            if stats["saved"]:
                log.info("В БД уже есть %s машин — лимит max_cars считается с учётом них", stats["saved"])
        except Exception:
            pass
    queue: asyncio.Queue = asyncio.Queue(maxsize=concurrency * 4)
    parser = EncarFullParser()
    stats_lock = asyncio.Lock()
    start_time = time.time()
    refill_done = False

    try:
        # Load pending from checkpoint into queue
        pending = checkpoint.pop_pending_batch(limit=concurrency * 100)
        for rec in pending:
            await queue.put(rec if len(rec) == 3 else (rec[0], rec[1], None))
        if pending:
            log.info("Resumed with %s pending IDs from checkpoint", len(pending))

        max_cars = int(max_cars_override if max_cars_override is not None else (config.get("max_cars", 0) or 0))
        if max_cars > 0:
            log.info("Run limited to max_cars=%s", max_cars)

        async with AsyncEncarClient(config, log) as client:
            if only_pending:
                producer = asyncio.create_task(asyncio.sleep(0))
            else:
                producer = asyncio.create_task(
                    list_producer(client, checkpoint, config, car_types, stats, log, max_cars=max_cars)
                )
            workers = [
                asyncio.create_task(
                    detail_worker(
                        i, client, checkpoint, storage, parser, config, queue, stats, log,
                        max_cars=max_cars,
                        stats_lock=stats_lock if max_cars > 0 else None,
                    )
                )
                for i in range(concurrency)
            ]
            # Feed queue from checkpoint periodically until no more pending or max_cars reached
            async def refill_queue():
                nonlocal refill_done
                while True:
                    await asyncio.sleep(15)
                    if max_cars > 0 and stats["saved"] >= max_cars:
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        log.info("Refill stopping: max_cars=%s reached (saved=%s)", max_cars, stats["saved"])
                        break
                    if queue.qsize() > concurrency * 3:
                        continue
                    batch = checkpoint.pop_pending_batch(limit=100)
                    for it in batch:
                        await queue.put(it)
                    if producer.done() and not batch and checkpoint.pending_count() == 0:
                        refill_done = True
                        for _ in workers:
                            await queue.put(None)
                        break
            refill_task = asyncio.create_task(refill_queue())
            # Stats logger
            async def log_stats():
                while not refill_done:
                    await asyncio.sleep(60)
                    p = checkpoint.pending_count()
                    log.info(
                        "Stats: processed=%s saved=%s detail_fail=%s parse_fail=%s pending=%s queue_size=%s",
                        stats["processed"], stats["saved"], stats["detail_fail"], stats["parse_fail"], p, queue.qsize(),
                    )
            stats_task = asyncio.create_task(log_stats())
            await producer
            # Keep refilling from pending until empty
            try:
                for refill_round in range(1000):
                    batch = checkpoint.pop_pending_batch(limit=100)
                    for it in batch:
                        await queue.put(it)
                    if not batch and checkpoint.pending_count() == 0:
                        break
                    await asyncio.sleep(0.3)
                await asyncio.gather(*workers)
            except asyncio.CancelledError:
                refill_done = True
                stats_task.cancel()
                try:
                    await stats_task
                except asyncio.CancelledError:
                    pass
                refill_task.cancel()
                try:
                    await refill_task
                except asyncio.CancelledError:
                    pass
                for _ in workers:
                    try:
                        queue.put_nowait(None)
                    except asyncio.QueueFull:
                        break
                await asyncio.gather(*workers, return_exceptions=True)
                raise
            refill_done = True
            stats_task.cancel()
            try:
                await stats_task
            except asyncio.CancelledError:
                pass
            refill_task.cancel()
            try:
                await refill_task
            except asyncio.CancelledError:
                pass

    finally:
        checkpoint.close()
        storage.close()

    elapsed = time.time() - start_time
    log.info(
        "Scraper finished. list_pages=%s ids_discovered=%s ids_queued=%s processed=%s saved=%s detail_fail=%s parse_fail=%s elapsed=%.1fs",
        stats["list_pages"], stats["ids_discovered"], stats["ids_queued"],
        stats["processed"], stats["saved"], stats["detail_fail"], stats["parse_fail"], elapsed,
    )
    try:
        power_stats = parser.get_power_stats()
        log.info(
            "Мощность: с мощностью=%s без мощности=%s",
            power_stats.get("with_power", 0), power_stats.get("without_power", 0),
        )
    except Exception:
        pass

    if backend == "sqlite" and isinstance(storage, SQLiteStorage):
        _run_export_to_frontend(storage.path, log)


def _run_export_to_frontend(db_path: str, log) -> None:
    """После парсинга экспортировать БД в frontend/cars.json."""
    path = Path(db_path).resolve()
    if not path.exists():
        log.warning("БД не найдена для экспорта: %s", path)
        return
    backend_dir = Path(__file__).resolve().parent
    repo_dir = backend_dir.parent
    out_path = repo_dir / "frontend" / "cars.json"
    export_script = backend_dir / "export_from_scraper_db.py"
    if not export_script.exists():
        log.warning("Скрипт экспорта не найден: %s", export_script)
        return
    export_args = [
        os.environ.get("PYTHON", sys.executable), str(export_script),
        "--db", str(path),
        "--out", str(out_path),
        "--chunk-size", "5000",
        "--chunk-dir", str(repo_dir / "frontend" / "data" / "chunks"),
        "--chunk-index", str(repo_dir / "frontend" / "data" / "cars.index.json"),
        "--gzip",
        "--learn-engine-map",
    ]
    if os.environ.get("SKIP_LEARN_ENGINE_MAP", "").strip().lower() in ("1", "true", "yes"):
        export_args = [a for a in export_args if a != "--learn-engine-map"]
    try:
        r = subprocess.run(
            export_args,
            cwd=str(backend_dir),
        )
        if r.returncode == 0:
            log.info("Экспорт в frontend/cars.json (+ chunks + gzip) выполнен")
        else:
            log.warning("Экспорт завершился с кодом %s", r.returncode)
    except Exception as e:
        log.warning("Ошибка экспорта на фронт: %s", e)


def main() -> None:
    import argparse
    _repo_root = Path(__file__).resolve().parent.parent
    _default_config = _repo_root / "scraper_config.yaml"
    p = argparse.ArgumentParser(description="Encar async scraper: list pages + detail workers")
    p.add_argument("--config", default=str(_default_config), help="Config YAML path (default: repo root)")
    p.add_argument("--max-cars", type=int, default=None, metavar="N", help="Stop after N cars saved (overrides config)")
    p.add_argument("--only-pending", action="store_true", help="Only process pending IDs from checkpoint (no list producer)")
    args = p.parse_args()
    asyncio.run(run_scraper(
        config_path=args.config,
        max_cars_override=args.max_cars,
        only_pending=args.only_pending,
    ))


if __name__ == "__main__":
    main()
