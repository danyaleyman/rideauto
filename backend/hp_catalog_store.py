from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "hp_catalog.db"

_NON_WORD_RE = re.compile(r"[^0-9a-zA-Z가-힣]+")


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def normalize_key_part(value: object) -> str:
    s = normalize_text(value).lower()
    return _NON_WORD_RE.sub("", s)


def parse_displacement_cc(value: object) -> Optional[int]:
    raw = normalize_text(value)
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    try:
        cc = int(digits)
    except ValueError:
        return None
    if 500 <= cc <= 10000:
        return cc
    return None


def parse_year_month(value: object) -> str:
    raw = normalize_text(value)
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 6:
        return digits[:6]
    if len(digits) == 4:
        return f"{digits}01"
    return ""


def parse_hp(value: object) -> Optional[int]:
    raw = normalize_text(value)
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    try:
        hp = int(digits)
    except ValueError:
        return None
    if 20 <= hp <= 2500:
        return hp
    return None


def hp_to_kw(hp: Optional[int]) -> Optional[float]:
    if hp is None:
        return None
    return round(float(hp) * 0.7355, 1)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS hp_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manufacturer TEXT NOT NULL,
            model TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '',
            engine_type TEXT NOT NULL DEFAULT '',
            displacement_cc INTEGER,
            drive TEXT NOT NULL DEFAULT '',
            year_month TEXT NOT NULL DEFAULT '',
            power_hp INTEGER,
            power_kw REAL,
            norm_manufacturer TEXT NOT NULL DEFAULT '',
            norm_model TEXT NOT NULL DEFAULT '',
            norm_version TEXT NOT NULL DEFAULT '',
            norm_engine_type TEXT NOT NULL DEFAULT '',
            llm_status TEXT NOT NULL DEFAULT 'pending',
            llm_model TEXT NOT NULL DEFAULT '',
            llm_reason TEXT NOT NULL DEFAULT '',
            llm_attempts INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'csv',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ux_hp_catalog_norm
        ON hp_catalog (
            norm_manufacturer,
            norm_model,
            norm_version,
            norm_engine_type,
            COALESCE(displacement_cc, -1),
            year_month
        );

        CREATE INDEX IF NOT EXISTS ix_hp_catalog_status ON hp_catalog (llm_status);
        CREATE INDEX IF NOT EXISTS ix_hp_catalog_hp ON hp_catalog (power_hp);
        """
    )
    conn.commit()
