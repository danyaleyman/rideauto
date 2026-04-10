"""Чекпоинт Encar в PostgreSQL: sync `Checkpoint` и async-обёртка с одним потоком + одним соединением."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, TypeVar

if TYPE_CHECKING:
    import psycopg2

T = TypeVar("T")

_log_checkpoint = logging.getLogger("encar.checkpoint")


@dataclass
class Checkpoint:
    """Синхронный чекпоинт (одно соединение). Вызывать только из одного потока или через `CheckpointAsync`."""

    dsn: str
    scope: str = "encar"
    max_pending: int = 500000
    _conn: Optional["psycopg2.extensions.connection"] = field(default=None, repr=False)

    def connect(self) -> None:
        import psycopg2

        self._conn = psycopg2.connect(self.dsn, connect_timeout=15)
        self._init_schema()
        assert self._conn is not None
        # Иначе один залипший на lock/query SELECT может вечно держать единственный поток CheckpointAsync.
        with self._conn.cursor() as cur:
            cur.execute("SET lock_timeout = '15s'")
            cur.execute("SET statement_timeout = '90s'")
        self._conn.commit()

    def _init_schema(self) -> None:
        assert self._conn is not None
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS scraper_checkpoint_state (
                    scope TEXT NOT NULL DEFAULT 'encar',
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY (scope, key)
                );
                CREATE TABLE IF NOT EXISTS scraper_pending_ids (
                    scope TEXT NOT NULL DEFAULT 'encar',
                    car_id TEXT NOT NULL,
                    car_type TEXT NOT NULL,
                    item_json TEXT,
                    added_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (scope, car_id)
                );
                CREATE INDEX IF NOT EXISTS idx_scraper_pending_added
                    ON scraper_pending_ids (scope, added_at);
                CREATE TABLE IF NOT EXISTS scraper_collected_ids (
                    scope TEXT NOT NULL DEFAULT 'encar',
                    car_id TEXT NOT NULL,
                    PRIMARY KEY (scope, car_id)
                );
                """
            )
        self._conn.commit()

    def get_state(self, key: str) -> Optional[str]:
        if not self._conn:
            return None
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM scraper_checkpoint_state WHERE scope = %s AND key = %s",
                (self.scope, key),
            )
            row = cur.fetchone()
            return str(row[0]) if row and row[0] is not None else None

    def set_state(self, key: str, value: str) -> None:
        if not self._conn:
            return
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper_checkpoint_state (scope, key, value)
                VALUES (%s, %s, %s)
                ON CONFLICT (scope, key) DO UPDATE SET value = EXCLUDED.value
                """,
                (self.scope, key, value),
            )
        self._conn.commit()

    def get_last_offset(self, car_type: str) -> int:
        v = self.get_state(f"list_offset_{car_type}")
        return int(v) if v else 0

    def set_last_offset(self, car_type: str, offset: int) -> None:
        self.set_state(f"list_offset_{car_type}", str(offset))

    def add_pending(self, car_id: str, car_type: str, item_json: Optional[str] = None) -> bool:
        if not self._conn:
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scraper_pending_ids (scope, car_id, car_type, item_json, added_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (scope, car_id) DO NOTHING
                    """,
                    (self.scope, car_id, car_type, item_json, time.time()),
                )
                ok = cur.rowcount > 0
            self._conn.commit()
            return ok
        except Exception:
            return False

    def add_pending_batch(self, items: List[Tuple[str, str, Optional[dict]]]) -> int:
        if not self._conn or not items:
            return 0
        now = time.time()
        added = 0
        with self._conn.cursor() as cur:
            for rec in items:
                car_id, car_type = rec[0], rec[1]
                item_j = json.dumps(rec[2], ensure_ascii=False) if len(rec) > 2 and rec[2] else None
                cur.execute(
                    """
                    INSERT INTO scraper_pending_ids (scope, car_id, car_type, item_json, added_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (scope, car_id) DO NOTHING
                    """,
                    (self.scope, car_id, car_type, item_j, now),
                )
                if cur.rowcount > 0:
                    added += 1
        self._conn.commit()
        return added

    def pop_pending_batch(self, limit: int) -> List[Tuple[str, str, Optional[dict]]]:
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                WITH sel AS (
                    SELECT car_id FROM scraper_pending_ids
                    WHERE scope = %s
                    ORDER BY added_at ASC
                    LIMIT %s
                )
                DELETE FROM scraper_pending_ids p
                USING sel s
                WHERE p.scope = %s AND p.car_id = s.car_id
                RETURNING p.car_id, p.car_type, p.item_json
                """,
                (self.scope, limit, self.scope),
            )
            rows = cur.fetchall()
        self._conn.commit()
        out: List[Tuple[str, str, Optional[dict]]] = []
        for r in rows:
            item = json.loads(r[2]) if r[2] else None
            out.append((str(r[0]), str(r[1]), item))
        return out

    def pending_count(self) -> int:
        if not self._conn:
            return 0
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM scraper_pending_ids WHERE scope = %s",
                (self.scope,),
            )
            r = cur.fetchone()
            return int(r[0]) if r and r[0] is not None else 0

    def is_collected(self, car_id: str) -> bool:
        if not self._conn:
            return False
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM scraper_collected_ids WHERE scope = %s AND car_id = %s LIMIT 1",
                (self.scope, car_id),
            )
            return cur.fetchone() is not None

    def mark_collected(self, car_id: str) -> None:
        if not self._conn:
            return
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper_collected_ids (scope, car_id)
                VALUES (%s, %s)
                ON CONFLICT (scope, car_id) DO NOTHING
                """,
                (self.scope, car_id),
            )
        self._conn.commit()

    def remove_collected(self, car_id: str) -> None:
        if not self._conn:
            return
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM scraper_collected_ids WHERE scope = %s AND car_id = %s",
                (self.scope, car_id),
            )
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


class CheckpointAsync:
    """
    Все операции чекпоинта в одном ThreadPoolExecutor (1 поток) + одно соединение `Checkpoint`.
    Event loop не блокируется psycopg2; нет гонок и шторма отдельных коннектов на каждый is_collected.
    """

    def __init__(self, dsn: str, scope: str = "encar", max_pending: int = 500000):
        self._dsn = dsn
        self._scope = scope
        self._max_pending = max_pending
        self._exec = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="enc_chk")
        self._inner: Optional[Checkpoint] = None

    def _connect_sync(self) -> None:
        if self._inner is not None:
            return
        self._inner = Checkpoint(dsn=self._dsn, scope=self._scope, max_pending=self._max_pending)
        self._inner.connect()

    async def connect(self) -> None:
        await asyncio.get_running_loop().run_in_executor(self._exec, self._connect_sync)

    def _close_sync(self) -> None:
        if self._inner is not None:
            self._inner.close()
            self._inner = None

    async def close(self) -> None:
        await asyncio.get_running_loop().run_in_executor(self._exec, self._close_sync)
        self._exec.shutdown(wait=True)

    def _ensure(self) -> Checkpoint:
        if self._inner is None:
            raise RuntimeError("CheckpointAsync: вызовите await connect()")
        return self._inner

    async def _run(self, fn: Callable[[Checkpoint], T]) -> T:
        def work() -> T:
            return fn(self._ensure())

        t0 = time.monotonic()
        try:
            return await asyncio.get_running_loop().run_in_executor(self._exec, work)
        finally:
            dt = time.monotonic() - t0
            if dt > 2.0:
                _log_checkpoint.warning("CheckpointAsync: операция %.2fs (медленно; всё чекпоинт-серийно)", dt)

    async def is_collected(self, car_id: str) -> bool:
        return await self._run(lambda cp: cp.is_collected(car_id))

    async def mark_collected(self, car_id: str) -> None:
        await self._run(lambda cp: cp.mark_collected(car_id))

    async def remove_collected(self, car_id: str) -> None:
        await self._run(lambda cp: cp.remove_collected(car_id))

    async def add_pending(self, car_id: str, car_type: str, item_json: Optional[str] = None) -> bool:
        return await self._run(lambda cp: cp.add_pending(car_id, car_type, item_json))

    async def add_pending_batch(self, items: List[Tuple[str, str, Optional[dict]]]) -> int:
        return await self._run(lambda cp: cp.add_pending_batch(items))

    async def pop_pending_batch(self, limit: int) -> List[Tuple[str, str, Optional[dict]]]:
        return await self._run(lambda cp: cp.pop_pending_batch(limit))

    async def pending_count(self) -> int:
        return await self._run(lambda cp: cp.pending_count())

    async def get_last_offset(self, car_type: str) -> int:
        return await self._run(lambda cp: cp.get_last_offset(car_type))

    async def set_last_offset(self, car_type: str, offset: int) -> None:
        await self._run(lambda cp: cp.set_last_offset(car_type, offset))
