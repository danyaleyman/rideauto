from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
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
            llm_confidence REAL,
            llm_prompt_version TEXT NOT NULL DEFAULT '',
            llm_prompt_hash TEXT NOT NULL DEFAULT '',
            review_flag INTEGER NOT NULL DEFAULT 0,
            review_note TEXT NOT NULL DEFAULT '',
            motor_code_norm TEXT NOT NULL DEFAULT '',
            vin_prefix TEXT NOT NULL DEFAULT '',
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
        CREATE INDEX IF NOT EXISTS ix_hp_catalog_review ON hp_catalog (review_flag);
        """
    )
    _ensure_hp_catalog_columns(conn)
    conn.commit()


def ensure_llm_prompt_cache_schema(conn: sqlite3.Connection) -> None:
    """Кеш повторных запросов с тем же промптом (полный SHA-256 ключ)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS hp_llm_prompt_cache (
            prompt_hash TEXT PRIMARY KEY,
            hp INTEGER NOT NULL,
            confidence REAL,
            raw_answer TEXT NOT NULL DEFAULT '',
            llm_prompt_version TEXT NOT NULL DEFAULT '',
            hit_count INTEGER NOT NULL DEFAULT 0,
            accessed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        CREATE INDEX IF NOT EXISTS ix_llm_prompt_cache_updated ON hp_llm_prompt_cache (updated_at);
        CREATE INDEX IF NOT EXISTS ix_llm_prompt_cache_accessed ON hp_llm_prompt_cache (accessed_at);
        CREATE TABLE IF NOT EXISTS hp_family_conflict_verdict (
            family_key TEXT PRIMARY KEY,
            verdict TEXT NOT NULL DEFAULT 'pending',
            notes TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        """
    )
    _ensure_llm_cache_extra_columns(conn)


def _ensure_llm_cache_extra_columns(conn: sqlite3.Connection) -> None:
    try:
        cur = conn.execute("PRAGMA table_info(hp_llm_prompt_cache)")
        have = {str(r[1]) for r in cur.fetchall()}
    except sqlite3.Error:
        return
    add: list[tuple[str, str]] = [
        ("hit_count", "INTEGER NOT NULL DEFAULT 0"),
        ("accessed_at", "TEXT NOT NULL DEFAULT ''"),
    ]
    for name, decl in add:
        if name not in have:
            conn.execute(f"ALTER TABLE hp_llm_prompt_cache ADD COLUMN {name} {decl}")
    conn.execute(
        """
        UPDATE hp_llm_prompt_cache SET accessed_at = updated_at WHERE accessed_at IS NULL OR accessed_at = ''
        """
    )


def llm_prompt_cache_get(conn: sqlite3.Connection, prompt_hash_full: str) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT hp, confidence, raw_answer, llm_prompt_version FROM hp_llm_prompt_cache
        WHERE prompt_hash = ?
        """,
        (prompt_hash_full,),
    )
    row = cur.fetchone()
    if row is not None:
        conn.execute(
            """
            UPDATE hp_llm_prompt_cache SET
              hit_count = hit_count + 1,
              accessed_at = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
              updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE prompt_hash = ?
            """,
            (prompt_hash_full,),
        )
    return row


def llm_prompt_cache_put(
    conn: sqlite3.Connection,
    *,
    prompt_hash_full: str,
    hp: int,
    confidence: Optional[float],
    raw_answer: str,
    llm_prompt_version: str,
) -> None:
    conn.execute(
        """
        INSERT INTO hp_llm_prompt_cache(prompt_hash, hp, confidence, raw_answer, llm_prompt_version, hit_count, accessed_at)
        VALUES (?, ?, ?, ?, ?, 0, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        ON CONFLICT(prompt_hash) DO UPDATE SET
            hp = excluded.hp,
            confidence = excluded.confidence,
            raw_answer = excluded.raw_answer,
            llm_prompt_version = excluded.llm_prompt_version,
            hit_count = hp_llm_prompt_cache.hit_count,
            accessed_at = hp_llm_prompt_cache.accessed_at,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (prompt_hash_full, hp, confidence, raw_answer[:2000], llm_prompt_version),
    )


def evict_llm_prompt_cache(conn: sqlite3.Connection, *, max_rows: int = 0, max_age_days: float = 0.0) -> int:
    """
    TTL по accessed_at и кап строк (LRU: самые давно необновляемые уходят первыми).
    """
    removed = 0
    cur = conn.execute("SELECT COUNT(*) FROM hp_llm_prompt_cache")
    before = int(cur.fetchone()[0])

    if max_age_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=float(max_age_days))
        cut_s = cutoff.strftime("%Y-%m-%dT%H:%M:%fZ")
        r = conn.execute(
            """
            DELETE FROM hp_llm_prompt_cache WHERE accessed_at <> '' AND accessed_at < ?
            """,
            (cut_s,),
        )
        removed += r.rowcount if r.rowcount else 0

    if max_rows > 0:
        cur2 = conn.execute("SELECT COUNT(*) FROM hp_llm_prompt_cache").fetchone()
        cnt = int(cur2[0]) if cur2 else 0
        over = cnt - int(max_rows)
        if over > 0:
            r2 = conn.execute(
                """
                DELETE FROM hp_llm_prompt_cache WHERE prompt_hash IN (
                    SELECT prompt_hash FROM hp_llm_prompt_cache
                    ORDER BY accessed_at ASC, updated_at ASC
                    LIMIT ?
                )
                """,
                (over,),
            )
            removed += r2.rowcount if r2.rowcount else 0

    cur_f = conn.execute("SELECT COUNT(*) FROM hp_llm_prompt_cache")
    after = int(cur_f.fetchone()[0])
    if max_rows <= 0 and max_age_days <= 0:
        return 0
    return max(0, before - after)


def family_conflict_canonical_key(norm_mfr: str, norm_model: str, norm_eng: str, dcc_sql: Any, ym: str) -> str:
    return f"{norm_mfr}|{norm_model}|{norm_eng}|{int(dcc_sql) if dcc_sql not in (None, '') else -1}|{ym}"


def verdict_bulk_get(conn: sqlite3.Connection, keys: list[str]) -> dict[str, sqlite3.Row]:
    out: dict[str, sqlite3.Row] = {}
    if not keys:
        return out
    chunk = 400
    for i in range(0, len(keys), chunk):
        sl = keys[i : i + chunk]
        placeholders = ",".join(["?"] * len(sl))
        q = f"""
            SELECT family_key, verdict, notes, operator, updated_at FROM hp_family_conflict_verdict
            WHERE family_key IN ({placeholders})
        """
        cur = conn.execute(q, tuple(sl))
        for r in cur.fetchall():
            out[str(r[0])] = r  # Row
    return out


def verdict_upsert(
    conn: sqlite3.Connection,
    *,
    family_key: str,
    verdict: str,
    notes: str = "",
    operator: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO hp_family_conflict_verdict (family_key, verdict, notes, operator)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(family_key) DO UPDATE SET
          verdict = excluded.verdict,
          notes = excluded.notes,
          operator = excluded.operator,
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
        """,
        (family_key, verdict.strip() or "pending", notes.strip(), operator.strip()),
    )


def _ensure_hp_catalog_columns(conn: sqlite3.Connection) -> None:
    """SQLite ALTER for DBs created before new columns existed."""
    try:
        cur = conn.execute("PRAGMA table_info(hp_catalog)")
        have = {str(r[1]) for r in cur.fetchall()}
    except sqlite3.Error:
        return
    alters: list[tuple[str, str]] = [
        ("llm_confidence", "REAL"),
        ("llm_prompt_version", "TEXT NOT NULL DEFAULT ''"),
        ("llm_prompt_hash", "TEXT NOT NULL DEFAULT ''"),
        ("review_flag", "INTEGER NOT NULL DEFAULT 0"),
        ("review_note", "TEXT NOT NULL DEFAULT ''"),
        ("motor_code_norm", "TEXT NOT NULL DEFAULT ''"),
        ("vin_prefix", "TEXT NOT NULL DEFAULT ''"),
    ]
    for col, decl in alters:
        if col not in have:
            conn.execute(f"ALTER TABLE hp_catalog ADD COLUMN {col} {decl}")
