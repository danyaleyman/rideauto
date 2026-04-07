"""Чекпоинт скрапера: состояние списка, pending id, collected — SQLite WAL."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Checkpoint:
    path: str
    max_pending: int
    conn: Optional[sqlite3.Connection] = field(default=None, repr=False)

    def connect(self) -> None:
        self.conn = sqlite3.connect(self.path, timeout=120.0)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        assert self.conn
        self.conn.executescript(
            """
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
        """
        )
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
