#!/usr/bin/env python3
"""
Lightweight API for large catalogs (100k+).

Run:
  python backend/api_server.py --db encar_cars.db --host 0.0.0.0 --port 8080
  # Китай: --db-china или WRA_CHINA_DB_PATH; иначе ищется encar_china.db рядом с --db или в backend/.

Кэш воркера (ускорение «тёплых» запросов):
  WRA_FACETS_CACHE_TTL, WRA_CATALOG_LIST_CACHE_TTL, WRA_CATALOG_LIST_CACHE_MAX_PAGE (1–2 страницы по умолчанию),
  WRA_CATALOG_LIST_CACHE=0 — отключить кэш ленты.
  Публичные GET /api/cars, /api/facets, /api/stats, /api/sort, /api/car/* — weak ETag + ответ 304 при If-None-Match (меньше трафика за прокси/CDN).
  Лимиты: WRA_RATE_LIMIT_GET_CARS_PER_MINUTE, WRA_RATE_LIMIT_GET_FACETS_PER_MINUTE (0 = выкл.).
  Глубокий offset: WRA_CATALOG_MAX_PAGE_OFFSET_ANON (по умолчанию 80; -1 = выкл.), без cursor для анонимов;
    авторизованные: WRA_CATALOG_MAX_PAGE_OFFSET_AUTH (0 = без лимита при валидной сессии).
  Sitemap: WRA_SITEMAP_MAX_URLS — URL на часть; индекс /api/sitemap/index.xml.
  Метрики: GET /api/metrics — только при WRA_PROMETHEUS_METRICS=1 (см. также wra_http_request_duration_ms_p95).
  Каталог в этом процессе — SQLite (отдельная БД Китая). PostgreSQL в пайплайне обновления; перенос чтения каталога в PG — отдельный объём (дублирование SQL/json).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from html import escape as html_escape_attr
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode
from xml.sax.saxutils import escape as xml_escape_text

from aiohttp import ClientSession, web

from encar_image_order import _sort_encar_image_url_list, _sort_h_images_list_entries

APP_DB_PATH = web.AppKey("db_path", str)
APP_CHINA_DB_PATH = web.AppKey("china_db_path", str)
APP_DB = web.AppKey("db", sqlite3.Connection)
APP_TELEGRAM_BOT_TOKEN = web.AppKey("telegram_bot_token", str)
APP_SUBSCRIPTIONS_ADMIN_KEY = web.AppKey("subscriptions_admin_key", str)
APP_PUBLIC_SITE_URL = web.AppKey("public_site_url", str)

_LOG = logging.getLogger("wra.api")
_RATE_BUCKETS: DefaultDict[str, List[float]] = defaultdict(list)
_RATE_LOCK = threading.Lock()
_RATE_WINDOW_SEC = 60.0

_METRICS_LOCK = threading.Lock()
_METRIC_REQUESTS: DefaultDict[Tuple[str, str, str], int] = defaultdict(int)  # (method, path_group, status)
_METRIC_DURATION_MS_SUM: DefaultDict[str, float] = defaultdict(float)  # path_group
_METRIC_DURATION_MS_COUNT: DefaultDict[str, int] = defaultdict(int)
_METRIC_DURATION_SAMPLES: DefaultDict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
_METRIC_304_COUNT = 0

_CAR_HTML_TEMPLATE_MTNS: Optional[int] = None
_CAR_HTML_TEMPLATE_TEXT: str = ""

_CATALOG_INDEX_LOCK = threading.Lock()
# Увеличивайте при добавлении индексов — существующие БД получат CREATE INDEX IF NOT EXISTS.
_CATALOG_INDEX_VERSION = 6
_CATALOG_INDEX_STATE: dict[str, int] = {}

_FACETS_CACHE_LOCK = threading.Lock()
# In-process TTL cache: повторные /api/facets с тем же query мгновенны (как edge/SWR у крупных площадок).
_FACETS_RESULT_CACHE: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Tuple[float, Dict[str, Any]]] = {}
_FACETS_CACHE_TTL_SEC = float(os.environ.get("WRA_FACETS_CACHE_TTL", "300"))
_FACETS_CACHE_MAX_ENTRIES = max(32, int(os.environ.get("WRA_FACETS_CACHE_MAX", "512")))

_CATALOG_LIST_CACHE_LOCK = threading.Lock()
_CATALOG_LIST_CACHE: Dict[Tuple[str, bool, Tuple[Tuple[str, str], ...]], Tuple[float, Dict[str, Any]]] = {}
_CATALOG_LIST_CACHE_TTL_SEC = float(os.environ.get("WRA_CATALOG_LIST_CACHE_TTL", "45"))
_CATALOG_LIST_CACHE_MAX_ENTRIES = max(16, int(os.environ.get("WRA_CATALOG_LIST_CACHE_MAX", "96")))
_CATALOG_LIST_CACHE_MAX_PAGE = max(1, int(os.environ.get("WRA_CATALOG_LIST_CACHE_MAX_PAGE", "2")))
_CATALOG_LIST_CACHE_MAX_PER_PAGE = min(100, max(12, int(os.environ.get("WRA_CATALOG_LIST_CACHE_MAX_PER_PAGE", "48"))))
_CATALOG_LIST_CACHE_ENABLED = os.environ.get("WRA_CATALOG_LIST_CACHE", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# Должно совпадать с GROUP BY в _catalog_listing_max_ids_subquery (иначе планировщик не использует индекс).
_LISTING_PARTITION_KEY_EXPR = (
    "COALESCE("
    "NULLIF(TRIM(json_extract(data_json, '$.data.inner_id')), ''), "
    "NULLIF(TRIM(json_extract(data_json, '$.inner_id')), ''), "
    "NULLIF(TRIM(json_extract(data_json, '$.data.id')), ''), "
    "car_id)"
)

# Китайский каталог в API — только Dongchedi (отдельный SQLite, см. WRA_CHINA_DB_PATH / --db-china).
_WRA_DONGCHEDI_SOURCE_SQL = "json_extract(data_json, '$.data.source') = 'dongchedi'"


def _catalog_query_is_china_market(q: Dict[str, str]) -> bool:
    src = (q.get("source") or "").strip().lower()
    reg = (q.get("region") or "").strip().lower()
    return src in ("china", "dongchedi") or reg == "china"


def _discover_china_db_if_unconfigured(korea_db_resolved: str) -> Optional[str]:
    """Если не заданы --db-china и WRA_CHINA_DB_PATH — ищем файл рядом с Кореей или в backend/.

    Типичный случай: выгрузка Dongchedi в encar_china.db, а API забыли с флагом.
    """
    root = Path(korea_db_resolved).resolve().parent
    for rel in ("encar_china.db", Path("backend") / "encar_china.db"):
        cand = root / rel
        try:
            if cand.is_file():
                return str(cand.resolve())
        except OSError:
            continue
    return None


def _db_has_any_dongchedi_row(conn: sqlite3.Connection) -> bool:
    """Без дедупа: нет ни одной строки source=dongchedi — пустой китайский каталог."""
    r = conn.execute(f"SELECT 1 FROM cars WHERE {_WRA_DONGCHEDI_SOURCE_SQL} LIMIT 1").fetchone()
    return r is not None


def _resolve_catalog_db_path(korea_db: str, china_db: Optional[str], query: Dict[str, str]) -> str:
    ch = (china_db or "").strip()
    if _catalog_query_is_china_market(query) and ch:
        return ch
    return korea_db


def _car_lookup_db_paths(korea_db: str, china_db: Optional[str], car_id: str) -> List[str]:
    """Сначала БД, где с высокой вероятностью лежит car_id (dongchedi-* → Китай)."""
    ch = (china_db or "").strip()
    cid = (car_id or "").strip().lower()
    if cid.startswith("dongchedi-") and ch:
        return [ch, korea_db]
    if ch:
        return [korea_db, ch]
    return [korea_db]


def _bootstrap_cars_table_if_missing(db_path: str) -> None:
    """Минимальная схема как у encar_scraper / dongchedi.scraper (для новой encar_china.db)."""
    conn = sqlite3.connect(db_path, timeout=60.0)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id TEXT UNIQUE NOT NULL,
                data_json TEXT NOT NULL,
                raw_json TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _dongchedi_db_listing_total_sync(db_path: str) -> int:
    where, params = _build_filter_sql({})
    from_frag, params2 = _cars_dedup_from_fragment(where, params)
    listing_ids = _catalog_listing_max_ids_subquery(from_frag)
    conn = _db_connect(db_path)
    try:
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM cars AS c INNER JOIN {listing_ids} AS x ON c.id = x.mid",
            params2,
        ).fetchone()
        return int(row["c"]) if row else 0
    finally:
        conn.close()


def _catalog_stats_merged_sync(korea_db: str, china_db: Optional[str]) -> Dict[str, Any]:
    """Счётчики Кореи с korea_db; china_listed — из отдельной china_db (если задана)."""
    base = _catalog_stats_korea_db_sync(korea_db)
    ch = (china_db or "").strip()
    if ch:
        try:
            rp = str(Path(ch).resolve())
            Path(rp).parent.mkdir(parents=True, exist_ok=True)
            _bootstrap_cars_table_if_missing(rp)
            _ensure_catalog_indexes(rp)
            base["china_listed"] = _dongchedi_db_listing_total_sync(rp)
        except Exception:
            _LOG.exception("catalog stats china db %s", ch)
            base["china_listed"] = 0
    return base


def _ensure_catalog_indexes(db_path: str) -> None:
    """Выраженные индексы под фильтры каталога (mark/model/цена/пробег/год/цвет/мощность/ДТП…).

    SQLite не позволяет индексировать подзапросы — сумма страховых выплат в ₽ и «повреждения»
    остаются без индекса (только страховые *случаи* как json_array_length можно).
    """
    try:
        rp = str(Path(db_path).resolve())
    except Exception:
        rp = db_path
    # Важно: держим lock на всё создание индексов. Иначе preload+catalog одновременно
    # запускают несколько CREATE INDEX — SQLite блокируется на десятки секунд, event loop
    # и пул потоков замирают (counts/cars/stats «pending», car page тоже).
    with _CATALOG_INDEX_LOCK:
        if _CATALOG_INDEX_STATE.get(rp, 0) >= _CATALOG_INDEX_VERSION:
            return
        try:
            conn = sqlite3.connect(db_path, timeout=120.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wra_cars_car_id_id ON cars(car_id, id DESC);
                    CREATE INDEX IF NOT EXISTS idx_wra_data_source ON cars(json_extract(data_json, '$.data.source'));
                    CREATE INDEX IF NOT EXISTS idx_wra_data_mark ON cars(json_extract(data_json, '$.data.mark'));
                    CREATE INDEX IF NOT EXISTS idx_wra_data_model ON cars(json_extract(data_json, '$.data.model'));
                    CREATE INDEX IF NOT EXISTS idx_wra_data_mark_model ON cars(
                        json_extract(data_json, '$.data.mark'),
                        json_extract(data_json, '$.data.model')
                    );
                    CREATE INDEX IF NOT EXISTS idx_wra_data_color ON cars(json_extract(data_json, '$.data.color'));
                    CREATE INDEX IF NOT EXISTS idx_wra_data_body_type ON cars(json_extract(data_json, '$.data.body_type'));
                    CREATE INDEX IF NOT EXISTS idx_wra_data_engine_type ON cars(json_extract(data_json, '$.data.engine_type'));
                    CREATE INDEX IF NOT EXISTS idx_wra_data_transmission_type ON cars(json_extract(data_json, '$.data.transmission_type'));
                    CREATE INDEX IF NOT EXISTS idx_wra_data_my_price ON cars(
                        CAST(json_extract(data_json, '$.data.my_price') AS REAL)
                    );
                    CREATE INDEX IF NOT EXISTS idx_wra_data_km_age ON cars(
                        CAST(json_extract(data_json, '$.data.km_age') AS INTEGER)
                    );
                    CREATE INDEX IF NOT EXISTS idx_wra_data_year ON cars(
                        CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER)
                    );
                    CREATE INDEX IF NOT EXISTS idx_wra_data_ym ON cars(
                        (CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.yearMonth'), json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER) * 12 +
                        CASE WHEN LENGTH(COALESCE(json_extract(data_json, '$.data.yearMonth'), '')) >= 6
                        THEN CAST(SUBSTR(json_extract(data_json, '$.data.yearMonth'), 5, 2) AS INTEGER) - 1 ELSE 0 END)
                    );
                    CREATE INDEX IF NOT EXISTS idx_wra_data_power ON cars(
                        COALESCE(
                            CAST(json_extract(data_json, '$.data.power') AS INTEGER),
                            CAST(json_extract(data_json, '$.data.hp') AS INTEGER),
                            CAST(json_extract(data_json, '$.power') AS INTEGER)
                        )
                    );
                    CREATE INDEX IF NOT EXISTS idx_wra_data_displacement ON cars(
                        CAST(json_extract(data_json, '$.data.displacement') AS INTEGER)
                    );
                    CREATE INDEX IF NOT EXISTS idx_wra_ins_cases ON cars(
                        COALESCE(json_array_length(json_extract(data_json, '$.data.extra.record_open.accidents')), 0)
                    );
                    """
                    + f"CREATE INDEX IF NOT EXISTS idx_wra_listing_partition_id ON cars ({_LISTING_PARTITION_KEY_EXPR}, id DESC);\n"
                )
                conn.commit()
                # Один раз после создания/обновления индексов — лучший план для JOIN + GROUP BY на больших БД.
                try:
                    conn.execute("PRAGMA analysis_limit=4000")
                except Exception:
                    pass
                try:
                    conn.execute("ANALYZE cars")
                except Exception:
                    pass
            finally:
                conn.close()
            _CATALOG_INDEX_STATE[rp] = _CATALOG_INDEX_VERSION
        except Exception:
            _LOG.exception("ensure catalog indexes failed for %s", rp)


def _db_connect(path: str) -> sqlite3.Connection:
    """Отдельное соединение на запрос чтения — WAL позволяет параллельным читателям не блокировать друг друга."""
    conn = sqlite3.connect(path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")
    # ~128 MiB page cache (отрицательное значение — в KiB)
    conn.execute("PRAGMA cache_size=-131072")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _init_app_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id TEXT NOT NULL UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            photo_url TEXT,
            raw_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_favorites (
            user_id INTEGER NOT NULL,
            car_id TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, car_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            car_id TEXT NOT NULL,
            viewed_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            filters_json TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_notified_car_pk INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checkout_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            car_ids_json TEXT NOT NULL,
            comment TEXT,
            contact TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_user_time ON user_history(user_id, viewed_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON user_subscriptions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_checkout_user ON checkout_requests(user_id)")
    # light migrations for existing DB
    sub_cols = [r["name"] for r in conn.execute("PRAGMA table_info(user_subscriptions)").fetchall()]
    if "last_notified_car_pk" not in sub_cols:
        conn.execute("ALTER TABLE user_subscriptions ADD COLUMN last_notified_car_pk INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def _parse_bearer_token(request: web.Request) -> str:
    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header.lower().startswith("bearer "):
        return ""
    return auth_header[7:].strip()


def _load_user_by_token(conn: sqlite3.Connection, token: str) -> Optional[sqlite3.Row]:
    if not token:
        return None
    now = _now_iso()
    row = conn.execute(
        """
        SELECT s.token, s.user_id, s.expires_at, u.*
        FROM user_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
          AND s.expires_at > ?
        LIMIT 1
        """,
        [token, now],
    ).fetchone()
    if not row:
        return None
    conn.execute("UPDATE user_sessions SET last_seen_at = ? WHERE token = ?", [now, token])
    conn.commit()
    return row


def _session_exists(conn: sqlite3.Connection, token: str) -> bool:
    """Проверка сессии без UPDATE last_seen (для лёгких порогов вроде лимита page)."""
    if not token:
        return False
    r = conn.execute(
        "SELECT 1 AS o FROM user_sessions WHERE token = ? AND expires_at > ? LIMIT 1",
        [token, _now_iso()],
    ).fetchone()
    return r is not None


def _env_int_signed(name: str, default: int) -> int:
    """Целое из env, в т.ч. отрицательное (-1 = выключить лимит в guard каталога)."""
    try:
        raw = (os.environ.get(name) or "").strip()
        if raw == "":
            return default
        return int(raw)
    except (TypeError, ValueError):
        return default


def _cars_offset_page_guard(request: web.Request, q: Dict[str, str]) -> Optional[web.Response]:
    """Дорогой OFFSET на SQLite без keyset: режем глубину page для анонимов (см. env)."""
    if (q.get("cursor") or "").strip():
        return None
    anon_cap = _env_int_signed("WRA_CATALOG_MAX_PAGE_OFFSET_ANON", 80)
    if anon_cap < 0:
        return None
    auth_cap = _env_int_signed("WRA_CATALOG_MAX_PAGE_OFFSET_AUTH", 0)
    try:
        page = int((q.get("page") or "1").strip() or "1")
    except ValueError:
        return None
    if page <= anon_cap:
        return None
    token = _parse_bearer_token(request)
    conn: sqlite3.Connection = request.app[APP_DB]
    if not token or not _session_exists(conn, token):
        return web.json_response(
            {
                "error": "deep_pagination_requires_cursor",
                "detail": "Для страниц с большим номером используйте курсор из meta.next_cursor (листание «вперёд») или войдите.",
                "max_page": anon_cap,
            },
            status=400,
            headers={"Cache-Control": "no-store"},
        )
    if auth_cap == 0:
        return None
    if page > auth_cap:
        return web.json_response(
            {
                "error": "deep_pagination_requires_cursor",
                "detail": f"Превышен лимит нумерации страниц ({auth_cap}). Используйте meta.next_cursor.",
                "max_page": auth_cap,
            },
            status=400,
            headers={"Cache-Control": "no-store"},
        )
    return None


def _auth_user_or_401(request: web.Request) -> Tuple[Optional[sqlite3.Connection], Optional[sqlite3.Row], Optional[web.Response]]:
    conn: sqlite3.Connection = request.app[APP_DB]
    token = _parse_bearer_token(request)
    user = _load_user_by_token(conn, token)
    if not user:
        return conn, None, web.json_response({"error": "unauthorized"}, status=401)
    return conn, user, None


async def _json_body(request: web.Request) -> Dict[str, Any]:
    try:
        payload = await request.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _verify_telegram_auth(payload: Dict[str, Any], bot_token: str) -> bool:
    tg_hash = str(payload.get("hash") or "").strip()
    auth_date = payload.get("auth_date")
    if not tg_hash or not auth_date:
        return False
    try:
        auth_ts = int(auth_date)
    except Exception:
        return False
    # 2 days window
    if abs(int(time.time()) - auth_ts) > 172800:
        return False
    pairs = []
    for k in sorted(payload.keys()):
        if k == "hash":
            continue
        v = payload.get(k)
        if v is None:
            continue
        pairs.append(f"{k}={v}")
    data_check_string = "\n".join(pairs)
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calc_hash = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc_hash, tg_hash)


def _extract_num(data: Dict[str, Any], key: str) -> float | None:
    try:
        value = data.get(key)
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _car_title(data: Dict[str, Any]) -> str:
    mark = (data.get("mark") or "").strip()
    model = (data.get("model") or "").strip()
    generation = (data.get("generation") or data.get("configuration") or "").strip()
    return " ".join([x for x in [mark, model, generation] if x]).strip()


# Поля карточки каталога (см. frontend/js/catalog.js draw). Без inspection/extra — детали в GET /api/car/{id}.
_SLIM_CATALOG_DATA_KEYS = frozenset(
    {
        "mark",
        "model",
        "generation",
        "configuration",
        "gradeName",
        "year",
        "yearMonth",
        "displacement",
        "engine_type",
        "drive_type",
        "prep_drive_type",
        "body_type",
        "transmission_type",
        "km_age",
        "offer_created",
        "created_at",
        "url",
        "inner_id",
        "my_price",
        "price_won",
        "price_calc_failed",
        "power",
        "hp",
        "outputHorsepower",
        "power_hp",
        "images",
        "h_images",
        "color",
        "krw_per_usdt",
        "usdt_rub",
        "source",
    }
)


def _trim_slim_list_field(slim_data: Dict[str, Any], key: str, max_items: int) -> None:
    """Урезаем списки URL/метаданных в slim-выдаче (карточка использует до 4 превью)."""
    if max_items < 1 or key not in slim_data:
        return
    v = slim_data[key]
    parsed: Any = None
    as_string = False
    if isinstance(v, str):
        as_string = True
        try:
            parsed = json.loads(v)
        except Exception:
            return
    elif isinstance(v, list):
        parsed = v
    else:
        return
    if not isinstance(parsed, list) or not parsed:
        return
    if key == "images":
        parsed = _sort_encar_image_url_list([x for x in parsed if isinstance(x, str)])
    elif key == "h_images":
        parsed = _sort_h_images_list_entries([x for x in parsed if isinstance(x, dict)])
    if len(parsed) > max_items:
        parsed = parsed[:max_items]
    slim_data[key] = json.dumps(parsed, ensure_ascii=False) if as_string else parsed


def _slim_catalog_car(car: Dict[str, Any], car_id: str) -> Dict[str, Any]:
    raw = car.get("data") if isinstance(car.get("data"), dict) else None
    if not isinstance(raw, dict):
        raw = car if isinstance(car, dict) else {}
    slim_data: Dict[str, Any] = {k: raw[k] for k in _SLIM_CATALOG_DATA_KEYS if k in raw}
    _trim_slim_list_field(slim_data, "images", 6)
    _trim_slim_list_field(slim_data, "h_images", 18)
    inner = raw.get("inner_id") if raw.get("inner_id") not in (None, "") else car.get("inner_id")
    if inner is not None and inner != "":
        slim_data["inner_id"] = inner
    out: Dict[str, Any] = {"id": car_id, "data": slim_data}
    _tid = car.get("inner_id") or slim_data.get("inner_id")
    if _tid is not None and _tid != "":
        out["inner_id"] = _tid
    out["title"] = _car_title(slim_data)
    out["price"] = _extract_num(slim_data, "my_price")
    out["year_num"] = int(str(slim_data.get("year") or 0)[:4] or 0)
    return out


def _csv_values(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _add_in_filter(clauses: List[str], params: List[str], expr: str, csv_raw: str | None) -> None:
    values = _csv_values(csv_raw)
    if not values:
        return
    placeholders = ",".join(["?"] * len(values))
    clauses.append(f"{expr} IN ({placeholders})")
    params.extend(values)


def _add_range_filter(clauses: List[str], params: List[str], expr: str, from_v: str | None, to_v: str | None) -> None:
    if from_v:
        clauses.append(f"{expr} >= ?")
        params.append(from_v)
    if to_v:
        clauses.append(f"{expr} <= ?")
        params.append(to_v)


def _build_filter_sql(query: Dict[str, str]) -> Tuple[str, List[str]]:
    clauses = []
    params: List[str] = []
    mark_expr = "json_extract(data_json, '$.data.mark')"
    model_expr = "json_extract(data_json, '$.data.model')"
    generation_expr = "COALESCE(json_extract(data_json, '$.data.generation'), json_extract(data_json, '$.data.configuration'))"
    trim_expr = "COALESCE(json_extract(data_json, '$.data.gradeName'), json_extract(data_json, '$.data.configuration'), json_extract(data_json, '$.data.generation'))"
    body_expr = "json_extract(data_json, '$.data.body_type')"
    fuel_expr = "json_extract(data_json, '$.data.engine_type')"
    trans_expr = "json_extract(data_json, '$.data.transmission_type')"
    drive_expr = "COALESCE(json_extract(data_json, '$.data.drive_type'), json_extract(data_json, '$.data.prep_drive_type'))"
    color_expr = "json_extract(data_json, '$.data.color')"
    power_expr = "COALESCE(CAST(json_extract(data_json, '$.data.power') AS INTEGER), CAST(json_extract(data_json, '$.data.hp') AS INTEGER), CAST(json_extract(data_json, '$.power') AS INTEGER))"
    engine_expr = "CAST(json_extract(data_json, '$.data.displacement') AS INTEGER)"
    # Фильтр «Цена» в интерфейсе задаётся в рублях (my_price под ключ)
    price_expr = "CAST(json_extract(data_json, '$.data.my_price') AS REAL)"
    mileage_expr = "CAST(json_extract(data_json, '$.data.km_age') AS INTEGER)"
    year_expr = "CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER)"
    ym_expr = (
        "(CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.yearMonth'), json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER) * 12 + "
        "CASE WHEN LENGTH(COALESCE(json_extract(data_json, '$.data.yearMonth'), '')) >= 6 "
        "THEN CAST(SUBSTR(json_extract(data_json, '$.data.yearMonth'), 5, 2) AS INTEGER) - 1 ELSE 0 END)"
    )
    insurance_cases_expr = "COALESCE(json_array_length(json_extract(data_json, '$.data.extra.record_open.accidents')), 0)"
    insurance_payout_expr = (
        "(SELECT COALESCE(SUM(CAST(json_extract(je.value, '$.insuranceBenefit') AS REAL)), 0) "
        "FROM json_each(COALESCE(json_extract(data_json, '$.data.extra.record_open.accidents'), '[]')) je)"
    )
    # Сумма выплат в строке инспекции — в вонах; сравнение с порогами в рублях по курсу из карточки
    insurance_payout_rub_expr = (
        f"(({insurance_payout_expr}) * (COALESCE(CAST(json_extract(data_json, '$.data.usdt_rub') AS REAL), 91.0) / "
        "NULLIF(COALESCE(CAST(json_extract(data_json, '$.data.krw_per_usdt') AS REAL), 1400.0), 0)))"
    )
    damaged_expr = "(SELECT COUNT(*) FROM json_each(COALESCE(json_extract(data_json, '$.data.extra.inspection_structured.bodyChanged'), '{}')))"

    _add_in_filter(clauses, params, mark_expr, query.get("marks"))
    _add_in_filter(clauses, params, model_expr, query.get("models"))
    _add_in_filter(clauses, params, generation_expr, query.get("generations"))
    _add_in_filter(clauses, params, trim_expr, query.get("trims"))
    _add_in_filter(clauses, params, body_expr, query.get("body"))
    _add_in_filter(clauses, params, fuel_expr, query.get("fuel"))
    _add_in_filter(clauses, params, trans_expr, query.get("trans"))
    _add_in_filter(clauses, params, color_expr, query.get("color"))

    _add_range_filter(clauses, params, power_expr, query.get("power_from"), query.get("power_to"))
    _add_range_filter(clauses, params, engine_expr, query.get("engine_from"), query.get("engine_to"))
    _add_range_filter(clauses, params, price_expr, query.get("price_from"), query.get("price_to"))
    _add_range_filter(clauses, params, mileage_expr, query.get("mileage_from"), query.get("mileage_to"))
    _add_range_filter(clauses, params, year_expr, query.get("year_from"), query.get("year_to"))
    _add_range_filter(clauses, params, ym_expr, query.get("ym_from"), query.get("ym_to"))
    _add_range_filter(clauses, params, insurance_cases_expr, query.get("ins_cases_from"), query.get("ins_cases_to"))
    _add_range_filter(clauses, params, insurance_payout_rub_expr, query.get("ins_payout_from"), query.get("ins_payout_to"))
    _add_range_filter(clauses, params, damaged_expr, query.get("damaged_from"), query.get("damaged_to"))

    if query.get("drive_awd") == "1":
        clauses.append(f"{drive_expr} = 'AWD'")
    if query.get("no_insurance_cases") == "1":
        clauses.append(f"{insurance_cases_expr} = 0")
    if query.get("no_insurance_payouts") == "1":
        clauses.append(f"{insurance_payout_expr} = 0")
    if query.get("no_damaged") == "1":
        clauses.append(f"{damaged_expr} = 0")
    if query.get("passage_cars") == "1":
        age_expr = (
            "(CAST(strftime('%Y', 'now') AS INTEGER) - "
            "CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER))"
        )
        clauses.append(f"{age_expr} BETWEEN 3 AND 5")

    src = (query.get("source") or "").strip().lower()
    region = (query.get("region") or "").strip().lower()
    # Только json_extract — совпадает с idx_wra_data_source; LOWER/TRIM по всей таблице даёт full scan и 504 на проде.
    # Явный source=encar важнее region=china (на случай тестовых URL).
    if src == "encar":
        _src_norm = (
            "COALESCE(NULLIF(TRIM(COALESCE(json_extract(data_json, '$.data.source'), '')), ''), 'encar')"
        )
        clauses.append(f"{_src_norm} = 'encar'")
    elif src == "dongchedi":
        clauses.append("json_extract(data_json, '$.data.source') = ?")
        params.append("dongchedi")
    elif src == "che168":
        clauses.append("1 = 0")
    elif src == "china" or region == "china":
        # source=china ИЛИ только region=china (если прокси/кэш отрезал source — иначе отдаётся весь каталог = «Корея»).
        clauses.append(_WRA_DONGCHEDI_SOURCE_SQL)
    elif region == "korea":
        _src_norm = (
            "COALESCE(NULLIF(TRIM(COALESCE(json_extract(data_json, '$.data.source'), '')), ''), 'encar')"
        )
        clauses.append(f"{_src_norm} = 'encar'")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


# Подзапрос «последняя версия строки по car_id»; JOIN часто предсказуемее для SQLite, чем IN (SELECT …).
_WRA_CAR_ID_DEDUP_JOIN = (
    "INNER JOIN (SELECT MAX(id) AS max_id FROM cars GROUP BY car_id) AS _wra_cd ON cars.id = _wra_cd.max_id"
)


def _cars_dedup_from_fragment(where: str, params: List[str]) -> Tuple[str, List[str]]:
    """Фрагмент сразу после «FROM cars»: AS cars + JOIN дедуп по car_id + при необходимости WHERE (фильтры)."""
    head = f"AS cars {_WRA_CAR_ID_DEDUP_JOIN}"
    if not where:
        return head, list(params)
    inner = where[6:].strip() if where.startswith("WHERE ") else where
    return f"{head} WHERE ({inner})", list(params)


def _sql_listing_partition_key_bare() -> str:
    """Одна строка каталога на объявление Encar: один inner id даже при разных car_id в БД."""
    return _LISTING_PARTITION_KEY_EXPR


def _sql_listing_partition_key_qualified(table_alias: str) -> str:
    """Тот же ключ партиции, с префиксом таблицы (для подзапросов / CTE)."""
    b = _sql_listing_partition_key_bare()
    return b.replace("data_json", f"{table_alias}.data_json").replace("car_id)", f"{table_alias}.car_id)")


def _catalog_listing_max_ids_subquery(from_fragment: str) -> str:
    """Одна строка каталога на объявление: MAX(id) по ключу партиции (эквивалент ROW_NUMBER…WHERE _rn=1).

    GROUP BY + MAX в SQLite на больших выборках часто заметно быстрее полного window sort.
    """
    pk = _sql_listing_partition_key_bare()
    return f"(SELECT MAX(cars.id) AS mid FROM cars {from_fragment} GROUP BY {pk})"


def _catalog_order_by_alias(order_sql: str, table_alias: str) -> str:
    return order_sql.replace("data_json", f"{table_alias}.data_json") + f", {table_alias}.id DESC"


def _catalog_query_dict(raw: Dict[str, str]) -> Dict[str, str]:
    skip = frozenset({"page", "per_page", "sort", "full", "cursor"})
    return {k: v for k, v in raw.items() if k not in skip and v not in (None, "")}


def _is_default_first_catalog_page(q: Dict[str, str]) -> bool:
    """Как preload на главной: нет фильтров, page=1, per_page=12, sort=date_new, не full=1."""
    if (q.get("full") or "").strip() == "1":
        return False
    qd = dict(_catalog_query_dict(q))
    src_low = (qd.get("source") or "").strip().lower()
    reg_low = (qd.get("region") or "").strip().lower()
    if src_low == "encar":
        qd.pop("source", None)
    if src_low == "dongchedi":
        qd.pop("source", None)
    if src_low == "china":
        qd.pop("source", None)
    if reg_low == "china":
        qd.pop("region", None)
    if reg_low == "korea":
        qd.pop("region", None)
    if qd:
        return False
    page = (q.get("page") or "1").strip() or "1"
    per = (q.get("per_page") or "12").strip() or "12"
    sort = (q.get("sort") or "date_new").strip() or "date_new"
    return page == "1" and per == "12" and sort == "date_new"


_CATALOG_SORT_SQL = {
    "date_new": "COALESCE(json_extract(data_json, '$.data.offer_created'), json_extract(data_json, '$.data.created_at')) DESC",
    "date_old": "COALESCE(json_extract(data_json, '$.data.offer_created'), json_extract(data_json, '$.data.created_at')) ASC",
    "year_new": "CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER) DESC",
    "year_old": "CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER) ASC",
    "price_high": "(CASE WHEN json_extract(data_json, '$.data.my_price') IS NULL OR json_extract(data_json, '$.data.my_price') = '' THEN 1 ELSE 0 END) ASC, CAST(json_extract(data_json, '$.data.my_price') AS REAL) DESC",
    "price_low": "(CASE WHEN json_extract(data_json, '$.data.my_price') IS NULL OR json_extract(data_json, '$.data.my_price') = '' THEN 1 ELSE 0 END) ASC, CAST(json_extract(data_json, '$.data.my_price') AS REAL) ASC",
    "mileage_high": "CAST(json_extract(data_json, '$.data.km_age') AS INTEGER) DESC",
    "mileage_low": "CAST(json_extract(data_json, '$.data.km_age') AS INTEGER) ASC",
}

# Мини-эндпоинт /api/sort (кэшируемый JSON) — UI по умолчанию из index.html; API для SPA/CDN.
_CATALOG_SORT_META: Tuple[Tuple[str, str, str], ...] = (
    ("date_new", "Сначала новые", "по дате объявления на Encar"),
    ("date_old", "Сначала старые", "по дате объявления"),
    ("year_new", "По году выпуска", "сначала более новые"),
    ("year_old", "По году выпуска", "сначала более ранние"),
    ("price_high", "По цене", "от дорогих к дешёвым"),
    ("price_low", "По цене", "от дешёвых к дорогим"),
    ("mileage_high", "По пробегу", "сначала с большим пробегом"),
    ("mileage_low", "По пробегу", "сначала с меньшим пробегом"),
)

_CATALOG_CURSOR_VER = 1


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> Optional[bytes]:
    if not s:
        return None
    pad = "=" * ((4 - len(s) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(s + pad)
    except Exception:
        return None


def _catalog_cursor_encode(d: Dict[str, Any]) -> str:
    return _b64url_encode(json.dumps(d, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _catalog_cursor_decode(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    b = _b64url_decode(raw.strip())
    if not b:
        return None
    try:
        d = json.loads(b.decode("utf-8"))
        if not isinstance(d, dict) or int(d.get("v", 0)) != _CATALOG_CURSOR_VER:
            return None
        return d
    except Exception:
        return None


def _catalog_ts_sql_u() -> str:
    return (
        "COALESCE(json_extract(u.data_json, '$.data.offer_created'), "
        "json_extract(u.data_json, '$.data.created_at'))"
    )


def _catalog_year_sql_u() -> str:
    return "CAST(SUBSTR(COALESCE(json_extract(u.data_json, '$.data.year'), ''), 1, 4) AS INTEGER)"


def _catalog_km_sql_u() -> str:
    return "CAST(json_extract(u.data_json, '$.data.km_age') AS INTEGER)"


def _catalog_price_nf_sql_u() -> str:
    return (
        "(CASE WHEN json_extract(u.data_json, '$.data.my_price') IS NULL "
        "OR json_extract(u.data_json, '$.data.my_price') = '' THEN 1 ELSE 0 END)"
    )


def _catalog_price_sql_u() -> str:
    return "CAST(json_extract(u.data_json, '$.data.my_price') AS REAL)"


def _catalog_cursor_extra_where(sort: str, cur: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    """Фрагмент AND (...) для keyset-пагинации; пустая строка если курсор не подходит."""
    if cur.get("s") != sort:
        return "", ()
    cid = cur.get("id")
    if not isinstance(cid, int):
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            return "", ()

    ts_sql = _catalog_ts_sql_u()
    y_sql = _catalog_year_sql_u()
    km_sql = _catalog_km_sql_u()

    if sort == "date_new":
        ts = cur.get("ts")
        if ts is None:
            return "", ()
        ts = str(ts)
        frag = f" AND (({ts_sql} < ?) OR ({ts_sql} = ? AND u.id < ?))"
        return frag, (ts, ts, cid)
    if sort == "date_old":
        ts = cur.get("ts")
        if ts is None:
            return "", ()
        ts = str(ts)
        frag = f" AND (({ts_sql} > ?) OR ({ts_sql} = ? AND u.id < ?))"
        return frag, (ts, ts, cid)
    if sort == "year_new":
        y = cur.get("y")
        try:
            yi = int(y)
        except (TypeError, ValueError):
            return "", ()
        frag = f" AND (({y_sql} < ?) OR ({y_sql} = ? AND u.id < ?))"
        return frag, (yi, yi, cid)
    if sort == "year_old":
        y = cur.get("y")
        try:
            yi = int(y)
        except (TypeError, ValueError):
            return "", ()
        frag = f" AND (({y_sql} > ?) OR ({y_sql} = ? AND u.id < ?))"
        return frag, (yi, yi, cid)
    if sort == "mileage_high":
        if "m" not in cur:
            return "", ()
        m = cur.get("m")
        try:
            mi = int(m)
        except (TypeError, ValueError):
            return "", ()
        frag = f" AND (({km_sql} < ?) OR ({km_sql} = ? AND u.id < ?))"
        return frag, (mi, mi, cid)
    if sort == "mileage_low":
        if "m" not in cur:
            return "", ()
        m = cur.get("m")
        try:
            mi = int(m)
        except (TypeError, ValueError):
            return "", ()
        frag = f" AND (({km_sql} > ?) OR ({km_sql} = ? AND u.id < ?))"
        return frag, (mi, mi, cid)
    if sort == "price_high":
        try:
            nf_c = int(cur.get("nf"))
        except (TypeError, ValueError):
            return "", ()
        nf_sql = _catalog_price_nf_sql_u()
        pr_sql = _catalog_price_sql_u()
        if nf_c == 0:
            if cur.get("pr") is None:
                return "", ()
            try:
                pr_f = float(cur["pr"])
            except (TypeError, ValueError):
                return "", ()
            frag = f""" AND (
                ({nf_sql} > ?)
                OR ({nf_sql} = ? AND {pr_sql} < ?)
                OR ({nf_sql} = ? AND {pr_sql} = ? AND u.id < ?)
            )"""
            return frag, (nf_c, nf_c, pr_f, nf_c, pr_f, cid)
        frag = f" AND ({nf_sql} = 1 AND u.id < ?)"
        return frag, (cid,)
    if sort == "price_low":
        try:
            nf_c = int(cur.get("nf"))
        except (TypeError, ValueError):
            return "", ()
        nf_sql = _catalog_price_nf_sql_u()
        pr_sql = _catalog_price_sql_u()
        if nf_c == 0:
            if cur.get("pr") is None:
                return "", ()
            try:
                pr_f = float(cur["pr"])
            except (TypeError, ValueError):
                return "", ()
            frag = f""" AND (
                ({nf_sql} > ?)
                OR ({nf_sql} = ? AND {pr_sql} > ?)
                OR ({nf_sql} = ? AND {pr_sql} = ? AND u.id < ?)
            )"""
            return frag, (nf_c, nf_c, pr_f, nf_c, pr_f, cid)
        frag = f" AND ({nf_sql} = 1 AND u.id < ?)"
        return frag, (cid,)
    return "", ()


def _catalog_build_cursor_payload(sort: str, row_id: int, data_json: str) -> Optional[Dict[str, Any]]:
    try:
        car = json.loads(data_json)
    except Exception:
        return None
    data = car.get("data") if isinstance(car.get("data"), dict) else car
    if not isinstance(data, dict):
        data = {}
    base: Dict[str, Any] = {"v": _CATALOG_CURSOR_VER, "s": sort, "id": row_id}
    if sort in ("date_new", "date_old"):
        ts = data.get("offer_created") or data.get("created_at") or ""
        base["ts"] = str(ts)
    elif sort in ("year_new", "year_old"):
        try:
            base["y"] = int(str(data.get("year") or "0")[:4] or 0)
        except ValueError:
            return None
    elif sort in ("mileage_high", "mileage_low"):
        v = data.get("km_age")
        if v is None or str(v).strip() == "":
            return None
        try:
            base["m"] = int(v)
        except (TypeError, ValueError):
            return None
    elif sort in ("price_high", "price_low"):
        mp = data.get("my_price")
        nf = 1 if mp is None or str(mp).strip() == "" else 0
        base["nf"] = nf
        if nf == 0:
            try:
                base["pr"] = float(mp)
            except (TypeError, ValueError):
                return None
        return base
    else:
        return None
    return base


def _cars_catalog_sync(db_path: str, query: Dict[str, str], *, slim: bool) -> Dict[str, Any]:
    t_wall0 = time.perf_counter()
    _ensure_catalog_indexes(db_path)
    conn = _db_connect(db_path)
    interrupt_ms = _env_int("WRA_SQLITE_CATALOG_INTERRUPT_MS", 0)
    src_log = (query.get("source") or "").strip() or (query.get("region") or "").strip() or "-"
    try:
        if interrupt_ms > 0:
            deadline = time.monotonic() + interrupt_ms / 1000.0

            def _prog() -> int:
                return 1 if time.monotonic() > deadline else 0

            conn.set_progress_handler(_prog, 8000)
        try:
            page = max(1, int(query.get("page", "1") or "1"))
            per_page = min(100, max(1, int(query.get("per_page", "12") or "12")))
            offset = (page - 1) * per_page

            where, params = _build_filter_sql(query)
            from_frag, params2 = _cars_dedup_from_fragment(where, params)
            if _catalog_query_is_china_market(query) and not _db_has_any_dongchedi_row(conn):
                return {
                    "result": [],
                    "meta": {
                        "page": page,
                        "per_page": per_page,
                        "total": 0,
                        "pages": 1,
                        "next_page": None,
                        "list_mode": "slim" if slim else "full",
                    },
                }
            sort = (query.get("sort") or "date_new").strip()
            order_sql = _CATALOG_SORT_SQL.get(sort, _CATALOG_SORT_SQL["date_new"])
            cur_raw = (query.get("cursor") or "").strip()
            cur_dec = _catalog_cursor_decode(cur_raw) if cur_raw else None
            cur_sql, cur_params = _catalog_cursor_extra_where(sort, cur_dec) if cur_dec else ("", ())
            use_cursor = bool(cur_sql)
            if use_cursor:
                offset = 0
            listing_ids = _catalog_listing_max_ids_subquery(from_frag)
            t_count0 = time.perf_counter()
            # Один проход: тяжёлый подзапрос listing_ids не дублируем (отдельный COUNT + SELECT давали 2× нагрузку).
            order_u = _catalog_order_by_alias(order_sql, "u")
            merged_sql = f"""
                SELECT u.car_id, u.data_json, u.id AS _wra_row_id, u._wra_tot
                FROM (
                    SELECT c.car_id, c.data_json, c.id,
                           COUNT(*) OVER () AS _wra_tot
                    FROM cars AS c
                    INNER JOIN {listing_ids} AS x ON c.id = x.mid
                ) AS u
                WHERE 1=1{cur_sql}
                ORDER BY {order_u}
                LIMIT ? OFFSET ?
                """
            rows = conn.execute(merged_sql, [*params2, *cur_params, per_page, offset]).fetchall()
            if rows:
                total = int(rows[0]["_wra_tot"])
            else:
                total = int(
                    conn.execute(
                        f"SELECT COUNT(*) AS c FROM cars AS c INNER JOIN {listing_ids} AS x ON c.id = x.mid",
                        params2,
                    ).fetchone()["c"]
                )
            t_count1 = time.perf_counter()

            result: List[Dict[str, Any]] = []
            for row in rows:
                car = json.loads(row["data_json"])
                car["id"] = row["car_id"]
                if slim:
                    result.append(_slim_catalog_car(car, row["car_id"]))
                else:
                    data = car.get("data") if isinstance(car.get("data"), dict) else car
                    if isinstance(data, dict):
                        car["title"] = _car_title(data)
                        car["price"] = _extract_num(data, "my_price")
                        car["year_num"] = int(str(data.get("year") or 0)[:4] or 0)
                    result.append(car)

            pages = max(1, (int(total) + per_page - 1) // per_page)
            meta_out: Dict[str, Any] = {
                "page": page,
                "per_page": per_page,
                "total": int(total),
                "pages": pages,
                "next_page": page + 1 if page < pages else None,
                "list_mode": "slim" if slim else "full",
            }
            if rows and len(rows) >= per_page:
                lr = rows[-1]
                pl = _catalog_build_cursor_payload(sort, int(lr["_wra_row_id"]), lr["data_json"])
                if pl:
                    meta_out["next_cursor"] = _catalog_cursor_encode(pl)
            _LOG.info(
                "catalog cars src=%s list_ms=%.0f total=%s rows=%s wall_ms=%.0f cursor=%s",
                src_log,
                (t_count1 - t_count0) * 1000,
                int(total),
                len(rows),
                (time.perf_counter() - t_wall0) * 1000,
                int(use_cursor),
            )
            return {"result": result, "meta": meta_out}
        finally:
            if interrupt_ms > 0:
                conn.set_progress_handler(None, 0)
    finally:
        conn.close()


def _cars_catalog_cache_key(db_path: str, q: Dict[str, str], slim: bool) -> Tuple[str, bool, Tuple[Tuple[str, str], ...]]:
    try:
        rp = str(Path(db_path).resolve())
    except Exception:
        rp = db_path
    frozen = tuple(sorted((str(k), str(v)) for k, v in q.items()))
    return (rp, slim, frozen)


def _cars_catalog_eligible_for_list_cache(q: Dict[str, str], slim: bool) -> bool:
    """Только slim-лента и первые страницы — как типичный «горячий» срез у маркетплейсов."""
    if not _CATALOG_LIST_CACHE_ENABLED or not slim:
        return False
    if (q.get("cursor") or "").strip():
        return False
    try:
        page = int((q.get("page") or "1").strip() or "1")
    except ValueError:
        return False
    if page < 1 or page > _CATALOG_LIST_CACHE_MAX_PAGE:
        return False
    try:
        per_page = int((q.get("per_page") or "12").strip() or "12")
    except ValueError:
        return False
    if per_page < 1 or per_page > _CATALOG_LIST_CACHE_MAX_PER_PAGE:
        return False
    return True


def _catalog_list_cache_prune_unlocked(now: float) -> None:
    ttl = _CATALOG_LIST_CACHE_TTL_SEC
    dead = [k for k, (ts, _) in _CATALOG_LIST_CACHE.items() if (now - ts) >= ttl]
    for k in dead:
        del _CATALOG_LIST_CACHE[k]
    while len(_CATALOG_LIST_CACHE) > _CATALOG_LIST_CACHE_MAX_ENTRIES:
        oldest_k = min(_CATALOG_LIST_CACHE.items(), key=lambda kv: kv[1][0])[0]
        del _CATALOG_LIST_CACHE[oldest_k]


def _cars_catalog_sync_memo(db_path: str, q: Dict[str, str], *, slim: bool) -> Dict[str, Any]:
    """Повторные запросы тех же страниц (Корея/Китай, те же фильтры) — из RAM воркера до TTL."""
    if not _cars_catalog_eligible_for_list_cache(q, slim):
        return _cars_catalog_sync(db_path, q, slim=slim)
    key = _cars_catalog_cache_key(db_path, q, slim)
    now = time.monotonic()
    with _CATALOG_LIST_CACHE_LOCK:
        ent = _CATALOG_LIST_CACHE.get(key)
        if ent is not None and (now - ent[0]) < _CATALOG_LIST_CACHE_TTL_SEC:
            return ent[1]
    payload = _cars_catalog_sync(db_path, q, slim=slim)
    with _CATALOG_LIST_CACHE_LOCK:
        _CATALOG_LIST_CACHE[key] = (time.monotonic(), payload)
        _catalog_list_cache_prune_unlocked(time.monotonic())
    return payload


_FACET_MARK = "json_extract(data_json, '$.data.mark')"
_FACET_MODEL = "json_extract(data_json, '$.data.model')"
_FACET_GENERATION = "COALESCE(json_extract(data_json, '$.data.generation'), json_extract(data_json, '$.data.configuration'))"
_FACET_TRIM = "COALESCE(json_extract(data_json, '$.data.gradeName'), json_extract(data_json, '$.data.configuration'), json_extract(data_json, '$.data.generation'))"
_FACET_BODY = "json_extract(data_json, '$.data.body_type')"
_FACET_FUEL = "json_extract(data_json, '$.data.engine_type')"
_FACET_TRANS = "json_extract(data_json, '$.data.transmission_type')"
_FACET_COLOR = "json_extract(data_json, '$.data.color')"

# (ключ ответа API, omit keys, SQL-выражение для одиночного запроса; колонки TEMP — _FACET_TEMP_COL)
_FACET_SPECS: Tuple[Tuple[str, frozenset[str], str], ...] = (
    ("marks", frozenset({"marks"}), _FACET_MARK),
    ("models", frozenset({"models"}), _FACET_MODEL),
    ("generations", frozenset({"generations"}), _FACET_GENERATION),
    ("trims", frozenset({"trims"}), _FACET_TRIM),
    ("bodies", frozenset({"body"}), _FACET_BODY),
    ("fuels", frozenset({"fuel"}), _FACET_FUEL),
    ("transmissions", frozenset({"trans"}), _FACET_TRANS),
    ("colors", frozenset({"color"}), _FACET_COLOR),
)
_FACET_TEMP_COL: Dict[str, str] = {
    "marks": "v_mark",
    "models": "v_model",
    "generations": "v_generation",
    "trims": "v_trim",
    "bodies": "v_body",
    "fuels": "v_fuel",
    "transmissions": "v_trans",
    "colors": "v_color",
}


def _catalog_stats_korea_db_sync(db_path: str) -> Dict[str, Any]:
    """Статистика по корейской БД (Encar). Счётчик Китая в ответе — 0 здесь; см. _catalog_stats_merged_sync."""
    _ensure_catalog_indexes(db_path)
    conn = _db_connect(db_path)
    try:
        today_str = datetime.now(timezone.utc).date().isoformat()
        from_frag, _np = _cars_dedup_from_fragment("", [])
        listing_ids = _catalog_listing_max_ids_subquery(from_frag)
        date_expr = (
            "substr(COALESCE(json_extract(c.data_json, '$.data.offer_created'), "
            "json_extract(c.data_json, '$.data.created_at')), 1, 10)"
        )
        row_today = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM cars AS c
            INNER JOIN {listing_ids} AS x ON c.id = x.mid
            WHERE {date_expr} = ?
            """,
            [today_str],
        ).fetchone()
        n = int(row_today["c"]) if row_today else 0
        _src_norm_c = (
            "COALESCE(NULLIF(TRIM(COALESCE(json_extract(c.data_json, '$.data.source'), '')), ''), 'encar')"
        )
        row_mix = conn.execute(
            f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN {_src_norm_c} = 'encar' THEN 1 ELSE 0 END) AS korea
            FROM cars AS c
            INNER JOIN {listing_ids} AS x ON c.id = x.mid
            """,
            [],
        ).fetchone()
        n_total = int(row_mix["total"]) if row_mix else 0
        korea = int(row_mix["korea"] or 0) if row_mix else 0
        return {
            "listed_today": n,
            "date_utc": today_str,
            "total": n_total,
            "korea_listed": korea,
            "china_listed": 0,
        }
    finally:
        conn.close()


def _norm_etag_token(raw: str) -> str:
    t = raw.strip()
    if t.startswith("W/"):
        t = t[2:].strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1]
    return t


def _if_none_match_satisfied(request: web.Request, etag: str) -> bool:
    inm = (request.headers.get("If-None-Match") or "").strip()
    if not inm:
        return False
    if inm == "*":
        return True
    want = _norm_etag_token(etag)
    for part in inm.split(","):
        if _norm_etag_token(part) == want:
            return True
    return False


def _json_public_cache(
    data: Any,
    cache_control: str,
    *,
    request: Optional[web.Request] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> web.Response:
    """JSON с Cache-Control; при request и совпадении If-None-Match — 304 без тела."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
    body_bytes = text.encode("utf-8")
    headers: Dict[str, str] = {"Cache-Control": cache_control, "ETag": f'W/"md5-{hashlib.md5(body_bytes).hexdigest()}"'}
    if extra_headers:
        headers.update(extra_headers)
    if request is not None and _if_none_match_satisfied(request, headers["ETag"]):
        return web.Response(status=304, headers=headers)
    resp = web.Response(body=body_bytes, content_type="application/json", charset="utf-8")
    for k, v in headers.items():
        resp.headers[k] = v
    return resp


def _cars_pagination_link(request: web.Request, payload: Dict[str, Any]) -> Optional[str]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    np = meta.get("next_page")
    if np is None:
        return None
    pairs = [(k, str(v)) for k, v in request.rel_url.query.items() if k not in ("page", "cursor")]
    nc = meta.get("next_cursor")
    if nc:
        pairs.append(("cursor", str(nc)))
    pairs.append(("page", str(int(np))))
    return f'</api/cars?{urlencode(pairs)}>; rel="next"'


def _site_base_url(request: web.Request) -> str:
    raw = (request.app.get(APP_PUBLIC_SITE_URL, "") or os.environ.get("PUBLIC_SITE_URL") or "").strip()
    if raw:
        return raw.rstrip("/")
    return "https://rideauto.ru"


def _metrics_path_group(path: str) -> str:
    if path == "/api/cars":
        return "cars"
    if path in ("/api/facets", "/api/filters"):
        return "facets"
    if path.startswith("/api/car/"):
        return "car"
    return "other"


def _sitemap_count_rows(db_path: str) -> int:
    if not db_path or not Path(db_path).is_file():
        return 0
    conn = _db_connect(db_path)
    try:
        r = conn.execute("SELECT COUNT(*) AS c FROM cars").fetchone()
        return int(r["c"]) if r else 0
    finally:
        conn.close()


def _sitemap_ids_slice(db_path: str, offset: int, limit: int) -> List[str]:
    if limit <= 0 or not db_path or not Path(db_path).is_file():
        return []
    conn = _db_connect(db_path)
    try:
        rows = conn.execute(
            "SELECT car_id FROM cars ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, max(0, offset)),
        ).fetchall()
        return [str(r[0]).strip() for r in rows if r[0] and str(r[0]).strip()]
    finally:
        conn.close()


def _sitemap_collect_car_ids_slice(korea_db: str, china_db: Optional[str], offset: int, limit: int) -> List[str]:
    """Срез глобальной ленты: сначала Корея по id DESC, затем Китай (как в однопроходном sitemap)."""
    china_path = str(Path(china_db).expanduser().resolve()) if china_db and str(china_db).strip() else ""
    nk = _sitemap_count_rows(korea_db)
    nc = _sitemap_count_rows(china_path) if china_path else 0
    if offset >= nk + nc:
        return []
    if offset < nk:
        take_k = min(limit, nk - offset)
        first = _sitemap_ids_slice(korea_db, offset, take_k)
        if len(first) >= limit:
            return first[:limit]
        rem = limit - len(first)
        if china_path and rem > 0:
            first.extend(_sitemap_ids_slice(china_path, 0, rem))
        return first[:limit]
    return _sitemap_ids_slice(china_path, offset - nk, limit)


def _sitemap_index_xml_body(base: str, korea_db: str, china_db: Optional[str], cap: int) -> str:
    china_path = str(Path(china_db).expanduser().resolve()) if china_db and str(china_db).strip() else ""
    total = _sitemap_count_rows(korea_db) + (_sitemap_count_rows(china_path) if china_path else 0)
    n_parts = max(1, (total + cap - 1) // cap) if total > 0 else 1
    base = base.rstrip("/")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <sitemap><loc>{xml_escape_text(base + '/sitemap-pages.xml')}</loc></sitemap>",
    ]
    for i in range(1, n_parts + 1):
        loc = f"{base}/api/sitemap/catalog.xml?part={i}"
        lines.append(f"  <sitemap><loc>{xml_escape_text(loc)}</loc></sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines) + "\n"


def _health_sqlite_probe(db_path: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"path": db_path, "readable": False}
    try:
        st = Path(db_path).stat()
        out["bytes"] = int(st.st_size)
        wal_p = Path(f"{db_path}-wal")
        shm_p = Path(f"{db_path}-shm")
        try:
            if wal_p.is_file():
                out["wal_bytes"] = int(wal_p.stat().st_size)
        except OSError:
            pass
        try:
            if shm_p.is_file():
                out["shm_bytes"] = int(shm_p.stat().st_size)
        except OSError:
            pass
    except OSError as e:
        out["stat_error"] = str(e)[:160]
        return out
    try:
        conn = _db_connect(db_path)
        try:
            conn.execute("SELECT 1 AS _ok").fetchone()
            out["readable"] = True
            try:
                uv = conn.execute("PRAGMA user_version").fetchone()
                out["pragma_user_version"] = int(uv[0]) if uv and uv[0] is not None else 0
            except sqlite3.Error:
                out["pragma_user_version"] = None
            cr = conn.execute("SELECT COUNT(*) AS c FROM cars").fetchone()
            out["cars_rows"] = int(cr["c"]) if cr else None
        finally:
            conn.close()
    except Exception as e:
        out["query_error"] = str(e)[:240]
    return out


def _car_html_template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "frontend" / "car.html"


def _load_car_html_template_text() -> str:
    global _CAR_HTML_TEMPLATE_MTNS, _CAR_HTML_TEMPLATE_TEXT
    p = _car_html_template_path()
    try:
        st = p.stat()
    except OSError:
        return ""
    mt = int(st.st_mtime_ns)
    if _CAR_HTML_TEMPLATE_MTNS == mt and _CAR_HTML_TEMPLATE_TEXT:
        return _CAR_HTML_TEMPLATE_TEXT
    _CAR_HTML_TEMPLATE_TEXT = p.read_text(encoding="utf-8")
    _CAR_HTML_TEMPLATE_MTNS = mt
    return _CAR_HTML_TEMPLATE_TEXT


def _first_car_image_url(d: Dict[str, Any]) -> str:
    for key in ("images", "h_images"):
        v = d.get(key)
        if isinstance(v, list) and v:
            u = v[0]
            if isinstance(u, str) and u.strip():
                return u.strip()
            if isinstance(u, dict):
                for k in ("url", "src", "photo"):
                    s = u.get(k)
                    if isinstance(s, str) and s.strip():
                        return s.strip()
    return ""


def _car_seo_head_block(canonical_url: str, page_title: str, description: str, og_image: str, car: Dict[str, Any]) -> str:
    d = car.get("data") if isinstance(car.get("data"), dict) else {}
    if not isinstance(d, dict):
        d = {}
    price = _extract_num(d, "my_price")
    brand = d.get("mark") or ""
    offers: Dict[str, Any] = {
        "@type": "Offer",
        "url": canonical_url,
        "availability": "https://schema.org/InStock",
        "priceCurrency": "RUB",
    }
    if price is not None:
        offers["price"] = price
    ld: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": page_title,
        "description": description[:500],
        "offers": offers,
    }
    if brand:
        ld["brand"] = {"@type": "Brand", "name": str(brand)}
    if og_image:
        ld["image"] = og_image
    og_fallback = "https://rideauto.ru/image/logo%20no%20text.svg"
    og_image_esc = html_escape_attr(og_image or og_fallback, quote=True)
    parts = [
        f"<title>{html_escape_attr(page_title, quote=True)}</title>",
        f'<meta name="description" content="{html_escape_attr(description[:320], quote=True)}">',
        f'<link rel="canonical" href="{html_escape_attr(canonical_url, quote=True)}">',
        f'<meta property="og:title" content="{html_escape_attr(page_title, quote=True)}">',
        f'<meta property="og:description" content="{html_escape_attr(description[:300], quote=True)}">',
        '<meta property="og:type" content="product">',
        f'<meta property="og:url" content="{html_escape_attr(canonical_url, quote=True)}">',
        f'<meta property="og:image" content="{og_image_esc}">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<script type="application/ld+json">'
        + json.dumps(ld, ensure_ascii=False, separators=(",", ":"))
        + "</script>",
    ]
    return "\n".join(parts) + "\n"


def _sitemap_catalog_xml_body(base: str, car_ids: List[str]) -> str:
    base = base.rstrip("/")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for cid in car_ids:
        loc = f"{base}/detail/{quote(cid, safe='')}"
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape_text(loc)}</loc>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("    <priority>0.7</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _facet_dimension_direct(
    conn: sqlite3.Connection,
    from_fragment: str,
    params2: List[str],
    value_expr: str,
) -> List[Dict[str, Any]]:
    """Один фасет: полный CTE (дорого по CPU, если вызывать 8 раз подряд)."""
    pk = _sql_listing_partition_key_bare()
    value_c = value_expr.replace("data_json", "c.data_json")
    sql = f"""
        WITH cand AS (
            SELECT cars.id AS id, cars.car_id AS car_id, cars.data_json AS data_json
            FROM cars
            {from_fragment}
        ),
        dedup AS (
            SELECT MAX(id) AS id
            FROM cand
            GROUP BY {pk}
        )
        SELECT {value_c} AS val, COUNT(*) AS c
        FROM cand AS c
        INNER JOIN dedup AS d ON c.id = d.id
        GROUP BY 1
        HAVING val IS NOT NULL AND CAST(val AS TEXT) <> ''
        ORDER BY val COLLATE NOCASE
    """
    rows = conn.execute(sql, params2).fetchall()
    return [{"value": r["val"], "count": r["c"]} for r in rows]


def _materialize_facet_narrow_temp(conn: sqlite3.Connection, from_fragment: str, params2: List[str]) -> None:
    """Один проход по cars → TEMP из 8 узких полей (без хранения целого data_json на каждую строку — иначе гигабайты RAM/диска)."""
    conn.execute("DROP TABLE IF EXISTS _wra_facet_cand")
    pk = _sql_listing_partition_key_bare()
    sql = f"""
        CREATE TEMP TABLE _wra_facet_cand AS
        WITH cand AS (
            SELECT cars.id AS id, cars.car_id AS car_id, cars.data_json AS data_json
            FROM cars
            {from_fragment}
        ),
        dedup AS (
            SELECT MAX(id) AS id
            FROM cand
            GROUP BY {pk}
        )
        SELECT
            json_extract(c.data_json, '$.data.mark') AS v_mark,
            json_extract(c.data_json, '$.data.model') AS v_model,
            COALESCE(
                json_extract(c.data_json, '$.data.generation'),
                json_extract(c.data_json, '$.data.configuration')
            ) AS v_generation,
            COALESCE(
                json_extract(c.data_json, '$.data.gradeName'),
                json_extract(c.data_json, '$.data.configuration'),
                json_extract(c.data_json, '$.data.generation')
            ) AS v_trim,
            json_extract(c.data_json, '$.data.body_type') AS v_body,
            json_extract(c.data_json, '$.data.engine_type') AS v_fuel,
            json_extract(c.data_json, '$.data.transmission_type') AS v_trans,
            json_extract(c.data_json, '$.data.color') AS v_color
        FROM cand AS c
        INNER JOIN dedup AS d ON c.id = d.id
    """
    conn.execute(sql, params2)


def _facet_from_narrow_temp(conn: sqlite3.Connection, facet_key: str) -> List[Dict[str, Any]]:
    col = _FACET_TEMP_COL[facet_key]
    sql = f"""
        SELECT {col} AS val, COUNT(*) AS c
        FROM _wra_facet_cand
        GROUP BY 1
        HAVING val IS NOT NULL AND CAST(val AS TEXT) <> ''
        ORDER BY val COLLATE NOCASE
    """
    rows = conn.execute(sql).fetchall()
    return [{"value": r["val"], "count": r["c"]} for r in rows]


def _facets_catalog_sync(db_path: str, q: Dict[str, str]) -> Dict[str, Any]:
    """Одинаковый SQL-фильтр у нескольких измерений → 1 scan + узкий TEMP + несколько дешёвых GROUP BY."""
    _ensure_catalog_indexes(db_path)
    empty_facets: Dict[str, List[Dict[str, Any]]] = {name: [] for name, _, _ in _FACET_SPECS}
    if _catalog_query_is_china_market(q):
        conn_probe = _db_connect(db_path)
        try:
            if not _db_has_any_dongchedi_row(conn_probe):
                return empty_facets
        finally:
            conn_probe.close()
    groups: DefaultDict[Tuple[str, Tuple[str, ...]], List[str]] = defaultdict(list)
    for name, omit_keys, _expr in _FACET_SPECS:
        q2 = {k: v for k, v in q.items() if k not in omit_keys}
        where, params = _build_filter_sql(q2)
        from_frag, params2 = _cars_dedup_from_fragment(where, params)
        groups[(from_frag, tuple(params2))].append(name)

    conn = _db_connect(db_path)
    try:
        acc: Dict[str, List[Dict[str, Any]]] = {}
        for (from_frag, params_t), names in groups.items():
            params2 = list(params_t)
            if len(names) >= 2:
                _materialize_facet_narrow_temp(conn, from_frag, params2)
                for facet_key in names:
                    acc[facet_key] = _facet_from_narrow_temp(conn, facet_key)
                conn.execute("DROP TABLE IF EXISTS _wra_facet_cand")
            else:
                only = names[0]
                _expr = next(e for n, _o, e in _FACET_SPECS if n == only)
                acc[only] = _facet_dimension_direct(conn, from_frag, params2, _expr)
        return {name: acc[name] for name, _, _ in _FACET_SPECS}
    finally:
        conn.close()


def _facets_cache_key(db_path: str, q: Dict[str, str]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
    try:
        rp = str(Path(db_path).resolve())
    except Exception:
        rp = db_path
    frozen = tuple(sorted((str(k), str(v)) for k, v in q.items()))
    return (rp, frozen)


def _facets_cache_prune_unlocked(now: float) -> None:
    ttl = _FACETS_CACHE_TTL_SEC
    dead = [k for k, (ts, _) in _FACETS_RESULT_CACHE.items() if (now - ts) >= ttl]
    for k in dead:
        del _FACETS_RESULT_CACHE[k]
    while len(_FACETS_RESULT_CACHE) > _FACETS_CACHE_MAX_ENTRIES:
        oldest_k = min(_FACETS_RESULT_CACHE.items(), key=lambda kv: kv[1][0])[0]
        del _FACETS_RESULT_CACHE[oldest_k]


def _facets_catalog_sync_memo(db_path: str, q: Dict[str, str]) -> Dict[str, Any]:
    """Тяжёлый SQL один раз на комбинацию параметров; далее до TTL — ответ из RAM воркера."""
    key = _facets_cache_key(db_path, q)
    now = time.monotonic()
    with _FACETS_CACHE_LOCK:
        ent = _FACETS_RESULT_CACHE.get(key)
        if ent is not None and (now - ent[0]) < _FACETS_CACHE_TTL_SEC:
            return ent[1]
    payload = _facets_catalog_sync(db_path, q)
    with _FACETS_CACHE_LOCK:
        _FACETS_RESULT_CACHE[key] = (time.monotonic(), payload)
        _facets_cache_prune_unlocked(time.monotonic())
    return payload


def _similar_rows(conn: sqlite3.Connection, current_car: Dict[str, Any], limit: int) -> List[sqlite3.Row]:
    d = current_car.get("data") if isinstance(current_car.get("data"), dict) else current_car
    if not isinstance(d, dict):
        return []
    mark = d.get("mark")
    price = d.get("price_won")
    if not mark or price is None:
        return []
    try:
        p = float(price)
    except Exception:
        return []
    pmin = p * 0.8
    pmax = p * 1.2
    lim = max(limit * 5, limit + 10)
    pk_base = _sql_listing_partition_key_qualified("base")
    # Именованные параметры — не перепутать порядок с «?» (раньше на проде ловили ProgrammingError 5 vs 6).
    rows = conn.execute(
        f"""
        WITH base AS (
            SELECT cars.car_id AS car_id, cars.data_json AS data_json, cars.id AS id
            FROM cars AS cars
            {_WRA_CAR_ID_DEDUP_JOIN}
            WHERE json_extract(cars.data_json, '$.data.mark') = :mark
              AND CAST(json_extract(cars.data_json, '$.data.price_won') AS REAL)
                  BETWEEN :pmin AND :pmax
        ),
        listed AS (
            SELECT MAX(base.id) AS mid FROM base GROUP BY {pk_base}
        )
        SELECT b.car_id, b.data_json
        FROM base AS b
        INNER JOIN listed AS l ON b.id = l.mid
        ORDER BY ABS(CAST(json_extract(b.data_json, '$.data.price_won') AS REAL) - :pcenter) ASC, b.id DESC
        LIMIT :lim
        """,
        {"mark": mark, "pmin": pmin, "pmax": pmax, "pcenter": p, "lim": lim},
    ).fetchall()
    return rows


async def health(request: web.Request) -> web.Response:
    body: Dict[str, Any] = {"status": "ok"}
    sha = (os.environ.get("WRA_GIT_SHA") or os.environ.get("GIT_COMMIT") or "").strip()
    if sha:
        body["git_sha"] = sha
    ch = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip()
    body["china_catalog_db"] = bool(ch)
    deep = request.rel_url.query.get("deep") == "1" or (os.environ.get("WRA_HEALTH_DEEP") or "").strip() == "1"
    if deep:
        korea_db = request.app[APP_DB_PATH]
        body["catalog_db"] = await asyncio.to_thread(_health_sqlite_probe, korea_db)
        if ch:
            body["china_catalog_db_probe"] = await asyncio.to_thread(_health_sqlite_probe, ch)
    return web.json_response(body)


async def prometheus_metrics(_: web.Request) -> web.Response:
    if (os.environ.get("WRA_PROMETHEUS_METRICS") or "").strip() != "1":
        return web.Response(status=404, body=b"metrics disabled\n", content_type="text/plain", charset="utf-8")
    lines: List[str] = []
    with _METRICS_LOCK:
        for (method, grp, status), n in sorted(_METRIC_REQUESTS.items()):
            lines.append(f'wra_http_requests_total{{method="{method}",route_group="{grp}",status="{status}"}} {n}')
        lines.append(f"wra_http_response_304_total {_METRIC_304_COUNT}")
        for grp in sorted(_METRIC_DURATION_MS_SUM.keys()):
            s = _METRIC_DURATION_MS_SUM[grp]
            c = max(1, _METRIC_DURATION_MS_COUNT[grp])
            lines.append(f'wra_http_request_duration_ms_avg{{route_group="{grp}"}} {s / c:.3f}')
        for grp, samples in sorted(_METRIC_DURATION_SAMPLES.items()):
            if not samples:
                continue
            arr = sorted(samples)
            idx = min(len(arr) - 1, max(0, int(round(0.95 * (len(arr) - 1)))))
            lines.append(f'wra_http_request_duration_ms_p95{{route_group="{grp}"}} {float(arr[idx]):.3f}')
    body = ("\n".join(lines) + "\n").encode("utf-8")
    return web.Response(body=body, content_type="text/plain", charset="utf-8")


async def api_version(_: web.Request) -> web.Response:
    """Версия деплоя для мониторинга и отладки (без кэша). Задайте WRA_GIT_SHA при деплое."""
    import sys

    sha = (os.environ.get("WRA_GIT_SHA") or os.environ.get("GIT_COMMIT") or "").strip()
    return web.json_response(
        {
            "service": "prod-encar-api",
            "git_sha": sha or None,
            "python": sys.version.split()[0],
        },
        headers={"Cache-Control": "no-store"},
    )


async def cars(request: web.Request) -> web.Response:
    q = {k: str(v) if not isinstance(v, str) else v for k, v in request.rel_url.query.items()}
    guard = _cars_offset_page_guard(request, q)
    if guard is not None:
        return guard
    slim = (q.get("full") or "").strip() != "1"
    korea_db = request.app[APP_DB_PATH]
    china_db = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip() or None
    db_path = _resolve_catalog_db_path(korea_db, china_db, q)
    try:
        payload = await asyncio.to_thread(lambda: _cars_catalog_sync_memo(db_path, q, slim=slim))
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            return web.json_response(
                {"error": "catalog_query_timeout", "detail": "sqlite_interrupt"},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        raise
    # Первая страница без фильтров (как у конкурента с «мгновенным» списком после preload) — дольше SWR у клиента.
    if slim and _is_default_first_catalog_page(q):
        cache = "public, max-age=120, stale-while-revalidate=600"
    elif slim:
        cache = "public, max-age=60, stale-while-revalidate=180"
    else:
        cache = "public, max-age=20, stale-while-revalidate=120"
    extra: Optional[Dict[str, str]] = None
    link = _cars_pagination_link(request, payload)
    if link:
        extra = {"Link": link}
    return _json_public_cache(payload, cache, request=request, extra_headers=extra)


async def facets(request: web.Request) -> web.Response:
    q = _catalog_query_dict({k: str(v) if not isinstance(v, str) else v for k, v in request.rel_url.query.items()})
    korea_db = request.app[APP_DB_PATH]
    china_db = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip() or None
    db_path = _resolve_catalog_db_path(korea_db, china_db, q)
    try:
        payload = await asyncio.to_thread(_facets_catalog_sync_memo, db_path, q)
    except Exception as e:
        return web.json_response(
            {"error": "facets_unavailable", "detail": str(e)[:500]},
            status=503,
            headers={"Cache-Control": "no-store"},
        )
    # Долгий stale-while-revalidate: браузер/CDN отдают прошлый JSON мгновенно, пока идёт фоновое обновление.
    return _json_public_cache(payload, "public, max-age=120, stale-while-revalidate=86400", request=request)


async def catalog_stats(request: web.Request) -> web.Response:
    korea_db = request.app[APP_DB_PATH]
    china_db = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip() or None
    payload = await asyncio.to_thread(_catalog_stats_merged_sync, korea_db, china_db)
    return _json_public_cache(payload, "public, max-age=90, stale-while-revalidate=600", request=request)


async def catalog_counts(request: web.Request) -> web.Response:
    """Как у конкурента: тот же payload, что /api/stats (+ total), отдельный URL для micro-cache."""
    return await catalog_stats(request)


async def catalog_sort_meta(request: web.Request) -> web.Response:
    opts = [{"value": v, "title": t, "hint": h} for v, t, h in _CATALOG_SORT_META]
    return _json_public_cache(
        {"options": opts},
        "public, max-age=3600, stale-while-revalidate=86400",
        request=request,
    )


async def sitemap_catalog_xml(request: web.Request) -> web.Response:
    """Sitemap urlset с публичными URL карточек /detail/{id}; part=1..N (шаг WRA_SITEMAP_MAX_URLS)."""
    cap = min(45000, max(1, _env_int("WRA_SITEMAP_MAX_URLS", 12000)))
    try:
        part = max(1, int((request.rel_url.query.get("part") or "1").strip() or "1"))
    except ValueError:
        part = 1
    offset = (part - 1) * cap
    base = _site_base_url(request)
    korea_db = request.app[APP_DB_PATH]
    china_raw = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip()
    china_db = china_raw or None
    car_ids = await asyncio.to_thread(_sitemap_collect_car_ids_slice, korea_db, china_db, offset, cap)
    body = _sitemap_catalog_xml_body(base, car_ids).encode("utf-8")
    headers: Dict[str, str] = {
        "Content-Type": "application/xml; charset=utf-8",
        "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
        "ETag": f'W/"md5-{hashlib.md5(body).hexdigest()}"',
    }
    if _if_none_match_satisfied(request, headers["ETag"]):
        return web.Response(status=304, headers=headers)
    resp = web.Response(body=body)
    for k, v in headers.items():
        resp.headers[k] = v
    return resp


async def sitemap_index_xml(request: web.Request) -> web.Response:
    cap = min(45000, max(1, _env_int("WRA_SITEMAP_MAX_URLS", 12000)))
    base = _site_base_url(request)
    korea_db = request.app[APP_DB_PATH]
    china_raw = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip()
    china_db = china_raw or None
    body = _sitemap_index_xml_body(base, korea_db, china_db, cap).encode("utf-8")
    headers: Dict[str, str] = {
        "Content-Type": "application/xml; charset=utf-8",
        "Cache-Control": "public, max-age=7200, stale-while-revalidate=86400",
        "ETag": f'W/"md5-{hashlib.md5(body).hexdigest()}"',
    }
    if _if_none_match_satisfied(request, headers["ETag"]):
        return web.Response(status=304, headers=headers)
    resp = web.Response(body=body)
    for k, v in headers.items():
        resp.headers[k] = v
    return resp


async def car_page_html(request: web.Request) -> web.Response:
    """Полный car.html с подстановкой title/OG/JSON-LD (для SEO без отдельного SSR). Nginx может проксировать /detail/{id} сюда."""
    car_id = (request.match_info.get("id") or "").strip()
    korea_db = request.app[APP_DB_PATH]
    china_db = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip() or None
    base = _site_base_url(request)
    tpl = _load_car_html_template_text()
    if not tpl:
        return web.Response(status=503, text="car.html template not found\n", content_type="text/plain", charset="utf-8")
    status, body = await asyncio.to_thread(_car_by_id_sync_multi, korea_db, china_db, request.match_info.get("id", "").strip())
    canonical = f"{base}/detail/{quote(car_id, safe='')}"
    if status != 200:
        nf = (
            "<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"UTF-8\">"
            '<meta name="robots" content="noindex">'
            f"<title>Объявление не найдено</title></head><body><p>Карточка недоступна.</p>"
            f'<p><a href="{html_escape_attr(base + "/", quote=True)}">В каталог</a></p></body></html>'
        )
        return web.Response(
            body=nf.encode("utf-8"),
            status=404,
            content_type="text/html",
            charset="utf-8",
            headers={"Cache-Control": "public, max-age=120"},
        )
    car = body.get("result") if isinstance(body.get("result"), dict) else {}
    d = car.get("data") if isinstance(car.get("data"), dict) else {}
    title_base = _car_title(d) if isinstance(d, dict) else car_id
    page_title = f"{title_base} — World Ride Auto" if title_base else f"Авто {car_id} — World Ride Auto"
    parts_desc: List[str] = []
    if isinstance(d, dict):
        if d.get("year"):
            parts_desc.append(str(d.get("year")))
        pr = _extract_num(d, "my_price")
        if pr is not None:
            parts_desc.append(f"{int(pr):,} ₽".replace(",", " "))
    description = (", ".join(parts_desc) + ". Доставка, растаможка — World Ride Auto.") if parts_desc else page_title
    og_img = _first_car_image_url(d) if isinstance(d, dict) else ""
    fragment = _car_seo_head_block(canonical, page_title, description, og_img, car)
    begin = "<!-- WRA_SEO_HEAD_BEGIN -->"
    end = "<!-- WRA_SEO_HEAD_END -->"
    if begin in tpl and end in tpl:
        i = tpl.index(begin) + len(begin)
        j = tpl.index(end)
        html_out = tpl[:i] + "\n" + fragment + tpl[j:]
    else:
        html_out = tpl.replace("<head>", "<head>\n" + fragment, 1)
    out_bytes = html_out.encode("utf-8")
    return web.Response(
        body=out_bytes,
        content_type="text/html",
        charset="utf-8",
        headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=3600"},
    )


def _car_row_by_any_id(conn: sqlite3.Connection, car_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT car_id, data_json
        FROM cars
        WHERE car_id = ?
           OR json_extract(data_json, '$.id') = ?
           OR json_extract(data_json, '$.inner_id') = ?
           OR json_extract(data_json, '$.data.inner_id') = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        [car_id, car_id, car_id, car_id],
    ).fetchone()


def _car_by_id_sync(db_path: str, car_id: str) -> Tuple[int, Dict[str, Any]]:
    if not car_id:
        return 400, {"error": "id is required"}
    conn = _db_connect(db_path)
    try:
        row = _car_row_by_any_id(conn, car_id)
        if not row:
            return 404, {"error": "not found"}
        car = json.loads(row["data_json"])
        car["id"] = row["car_id"]
        return 200, {"result": car}
    finally:
        conn.close()


def _car_by_id_sync_multi(korea_db: str, china_db: Optional[str], car_id: str) -> Tuple[int, Dict[str, Any]]:
    if not car_id:
        return 400, {"error": "id is required"}
    for dp in _car_lookup_db_paths(korea_db, china_db, car_id):
        st, body = _car_by_id_sync(dp, car_id)
        if st == 200:
            return st, body
    return 404, {"error": "not found"}


def _similar_sync(db_path: str, car_id: str, limit: int) -> Dict[str, Any]:
    if not car_id:
        return {"result": [], "meta": {"limit": limit}}
    conn = _db_connect(db_path)
    try:
        row = _car_row_by_any_id(conn, car_id)
        if not row:
            return {"result": [], "meta": {"limit": limit}}
        current = json.loads(row["data_json"])
        current_id = str(row["car_id"])
        rows = _similar_rows(conn, current, limit)
        result: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_keys: set[str] = set()
        for r in rows:
            cid = str(r["car_id"])
            if cid == current_id or cid in seen_ids:
                continue
            car = json.loads(r["data_json"])
            car["id"] = cid
            d = car.get("data") if isinstance(car.get("data"), dict) else {}
            key = f"{d.get('mark','')}|{d.get('model','')}|{d.get('year','')}|{d.get('km_age','')}|{d.get('price_won','')}"
            if key in seen_keys:
                continue
            seen_ids.add(cid)
            seen_keys.add(key)
            result.append(car)
            if len(result) >= limit:
                break
        return {"result": result, "meta": {"limit": limit, "count": len(result)}}
    finally:
        conn.close()


def _similar_sync_multi(korea_db: str, china_db: Optional[str], car_id: str, limit: int) -> Dict[str, Any]:
    for dp in _car_lookup_db_paths(korea_db, china_db, car_id):
        st, _ = _car_by_id_sync(dp, car_id)
        if st == 200:
            return _similar_sync(dp, car_id, limit)
    return {"result": [], "meta": {"limit": limit, "count": 0}}


def _compare_cars_sync(korea_db: str, china_db: Optional[str], ids: List[str]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for cid in ids:
        row = None
        for dp in _car_lookup_db_paths(korea_db, china_db, cid):
            conn = _db_connect(dp)
            try:
                row = _car_row_by_any_id(conn, cid)
                if row:
                    break
            finally:
                conn.close()
        if not row:
            continue
        car = json.loads(row["data_json"])
        car["id"] = row["car_id"]
        d = car.get("data") if isinstance(car.get("data"), dict) else {}
        result.append(
            {
                "id": car["id"],
                "title": _car_title(d),
                "price_rub": _extract_num(d, "my_price"),
                "km_age": d.get("km_age"),
                "power": d.get("power"),
                "displacement": d.get("displacement"),
                "year": d.get("year"),
                "customs_total_rub": d.get("customs_total_rub"),
            }
        )
    return result


async def car_by_id(request: web.Request) -> web.Response:
    car_id = request.match_info.get("id", "").strip()
    korea_db = request.app[APP_DB_PATH]
    china_db = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip() or None
    status, body = await asyncio.to_thread(_car_by_id_sync_multi, korea_db, china_db, car_id)
    if status == 200:
        return _json_public_cache(body, "public, max-age=45, stale-while-revalidate=300", request=request)
    return web.json_response(body, status=status)


async def similar(request: web.Request) -> web.Response:
    car_id = (request.rel_url.query.get("car_id") or "").strip()
    try:
        limit = min(20, max(1, int(request.rel_url.query.get("limit", "8"))))
    except (TypeError, ValueError):
        limit = 8
    korea_db = request.app[APP_DB_PATH]
    china_db = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip() or None
    payload = await asyncio.to_thread(_similar_sync_multi, korea_db, china_db, car_id, limit)
    return web.json_response(payload)


async def auth_telegram(request: web.Request) -> web.Response:
    conn: sqlite3.Connection = request.app[APP_DB]
    bot_token = request.app.get(APP_TELEGRAM_BOT_TOKEN, "") or ""
    if not bot_token:
        return web.json_response({"error": "TELEGRAM_BOT_TOKEN is not configured"}, status=503)
    payload = await _json_body(request)
    if not _verify_telegram_auth(payload, bot_token):
        return web.json_response({"error": "invalid telegram auth payload"}, status=400)
    tg_id = str(payload.get("id") or "").strip()
    if not tg_id:
        return web.json_response({"error": "id is required"}, status=400)

    now = _now_iso()
    conn.execute(
        """
        INSERT INTO users (tg_id, username, first_name, last_name, photo_url, raw_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tg_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            photo_url = excluded.photo_url,
            raw_json = excluded.raw_json,
            updated_at = excluded.updated_at
        """,
        [
            tg_id,
            payload.get("username"),
            payload.get("first_name"),
            payload.get("last_name"),
            payload.get("photo_url"),
            json.dumps(payload, ensure_ascii=False),
            now,
            now,
        ],
    )
    user = conn.execute("SELECT * FROM users WHERE tg_id = ? LIMIT 1", [tg_id]).fetchone()
    token = secrets.token_urlsafe(40)
    expires_at = (
        datetime.fromtimestamp(int(time.time()) + 60 * 60 * 24 * 30, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    conn.execute(
        "INSERT INTO user_sessions (token, user_id, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
        [token, user["id"], now, expires_at, now],
    )
    conn.commit()
    return web.json_response(
        {
            "token": token,
            "expires_at": expires_at,
            "user": {
                "id": user["id"],
                "tg_id": user["tg_id"],
                "username": user["username"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "photo_url": user["photo_url"],
            },
        }
    )


async def me(request: web.Request) -> web.Response:
    _conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    return web.json_response(
        {
            "user": {
                "id": user["id"],
                "tg_id": user["tg_id"],
                "username": user["username"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "photo_url": user["photo_url"],
            }
        }
    )


async def logout(request: web.Request) -> web.Response:
    conn: sqlite3.Connection = request.app[APP_DB]
    token = _parse_bearer_token(request)
    if token:
        conn.execute("DELETE FROM user_sessions WHERE token = ?", [token])
        conn.commit()
    return web.json_response({"ok": True})


async def favorites_list(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    rows = conn.execute(
        "SELECT car_id, note, created_at, updated_at FROM user_favorites WHERE user_id = ? ORDER BY updated_at DESC",
        [user["id"]],
    ).fetchall()
    return web.json_response({"result": [dict(r) for r in rows]})


async def favorites_add(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    payload = await _json_body(request)
    car_id = str(payload.get("car_id") or "").strip()
    if not car_id:
        return web.json_response({"error": "car_id is required"}, status=400)
    note = str(payload.get("note") or "").strip() or None
    if not _car_row_by_any_id(conn, car_id):
        return web.json_response({"error": "car not found"}, status=404)
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO user_favorites (user_id, car_id, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, car_id) DO UPDATE SET
            note = excluded.note,
            updated_at = excluded.updated_at
        """,
        [user["id"], car_id, note, now, now],
    )
    conn.commit()
    return web.json_response({"ok": True})


async def favorites_remove(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    car_id = request.match_info.get("car_id", "").strip()
    conn.execute("DELETE FROM user_favorites WHERE user_id = ? AND car_id = ?", [user["id"], car_id])
    conn.commit()
    return web.json_response({"ok": True})


async def history_add(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    payload = await _json_body(request)
    car_id = str(payload.get("car_id") or "").strip()
    if not car_id:
        return web.json_response({"error": "car_id is required"}, status=400)
    if not _car_row_by_any_id(conn, car_id):
        return web.json_response({"error": "car not found"}, status=404)
    now = _now_iso()
    conn.execute("INSERT INTO user_history (user_id, car_id, viewed_at) VALUES (?, ?, ?)", [user["id"], car_id, now])
    # keep only latest 300
    conn.execute(
        """
        DELETE FROM user_history
        WHERE user_id = ?
          AND id NOT IN (
            SELECT id FROM user_history
            WHERE user_id = ?
            ORDER BY viewed_at DESC, id DESC
            LIMIT 300
          )
        """,
        [user["id"], user["id"]],
    )
    conn.commit()
    return web.json_response({"ok": True})


async def history_list(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    limit = min(200, max(1, int(request.rel_url.query.get("limit", "30"))))
    rows = conn.execute(
        "SELECT car_id, viewed_at FROM user_history WHERE user_id = ? ORDER BY viewed_at DESC, id DESC LIMIT ?",
        [user["id"], limit],
    ).fetchall()
    return web.json_response({"result": [dict(r) for r in rows]})


async def subscriptions_list(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    rows = conn.execute(
        """
        SELECT id, name, filters_json, is_active, created_at, updated_at
        FROM user_subscriptions
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        [user["id"]],
    ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        try:
            item["filters"] = json.loads(item.pop("filters_json") or "{}")
        except Exception:
            item["filters"] = {}
            item.pop("filters_json", None)
        item["is_active"] = bool(item.get("is_active"))
        result.append(item)
    return web.json_response({"result": result})


async def subscriptions_add(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    payload = await _json_body(request)
    name = str(payload.get("name") or "").strip() or "Подписка"
    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO user_subscriptions (user_id, name, filters_json, is_active, created_at, updated_at)
        VALUES (?, ?, ?, 1, ?, ?)
        """,
        [user["id"], name[:120], json.dumps(filters, ensure_ascii=False), now, now],
    )
    conn.commit()
    return web.json_response({"ok": True})


async def subscriptions_remove(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    sid = request.match_info.get("sid", "").strip()
    conn.execute("DELETE FROM user_subscriptions WHERE id = ? AND user_id = ?", [sid, user["id"]])
    conn.commit()
    return web.json_response({"ok": True})


async def compare(request: web.Request) -> web.Response:
    ids = [x.strip() for x in (request.rel_url.query.get("ids") or "").split(",") if x.strip()]
    ids = ids[:4]
    korea_db = request.app[APP_DB_PATH]
    china_db = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip() or None
    result = await asyncio.to_thread(_compare_cars_sync, korea_db, china_db, ids)
    return web.json_response({"result": result})


async def checkout_create(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    payload = await _json_body(request)
    car_ids = payload.get("car_ids")
    if not isinstance(car_ids, list) or not car_ids:
        return web.json_response({"error": "car_ids is required"}, status=400)
    car_ids = [str(x).strip() for x in car_ids if str(x).strip()][:20]
    comment = str(payload.get("comment") or "").strip() or None
    contact = str(payload.get("contact") or "").strip() or None
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO checkout_requests (user_id, car_ids_json, comment, contact, status, created_at)
        VALUES (?, ?, ?, ?, 'new', ?)
        """,
        [user["id"], json.dumps(car_ids, ensure_ascii=False), comment, contact, now],
    )
    conn.commit()
    return web.json_response({"ok": True})


async def checkout_list(request: web.Request) -> web.Response:
    conn, user, err = _auth_user_or_401(request)
    if err:
        return err
    rows = conn.execute(
        """
        SELECT id, car_ids_json, comment, contact, status, created_at
        FROM checkout_requests
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 100
        """,
        [user["id"]],
    ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        try:
            item["car_ids"] = json.loads(item.pop("car_ids_json") or "[]")
        except Exception:
            item["car_ids"] = []
            item.pop("car_ids_json", None)
        result.append(item)
    return web.json_response({"result": result})


def _subscription_filters_to_query(filters: Dict[str, Any]) -> Dict[str, str]:
    q: Dict[str, str] = {}
    for k, v in (filters or {}).items():
        if isinstance(v, list):
            q[k] = ",".join([str(x) for x in v if str(x).strip()])
        elif v is None:
            continue
        else:
            q[k] = str(v)
    return q


async def _send_tg_message(bot_token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:3900], "disable_web_page_preview": True}
    try:
        async with ClientSession() as session:
            async with session.post(url, json=payload, timeout=12) as resp:
                return 200 <= resp.status < 300
    except Exception:
        return False


async def run_subscription_notifications(request: web.Request) -> web.Response:
    admin_key_env = (request.app.get(APP_SUBSCRIPTIONS_ADMIN_KEY, "") or "").strip()
    if not admin_key_env:
        return web.json_response({"error": "SUBSCRIPTIONS_ADMIN_KEY is not configured"}, status=503)
    admin_key = request.headers.get("X-Admin-Key", "").strip()
    if not admin_key or admin_key != admin_key_env:
        return web.json_response({"error": "forbidden"}, status=403)
    bot_token = (request.app.get(APP_TELEGRAM_BOT_TOKEN, "") or "").strip()
    if not bot_token:
        return web.json_response({"error": "TELEGRAM_BOT_TOKEN is not configured"}, status=503)

    conn: sqlite3.Connection = request.app[APP_DB]
    korea_db = request.app[APP_DB_PATH]
    china_db = (request.app.get(APP_CHINA_DB_PATH, "") or "").strip() or None
    site_url = (request.app.get(APP_PUBLIC_SITE_URL, "") or "").rstrip("/")
    sub_rows = conn.execute(
        """
        SELECT s.id, s.user_id, s.name, s.filters_json, s.last_notified_car_pk, u.tg_id
        FROM user_subscriptions s
        JOIN users u ON u.id = s.user_id
        WHERE s.is_active = 1
        ORDER BY s.id ASC
        """
    ).fetchall()
    sent = 0
    checked = 0
    for row in sub_rows:
        checked += 1
        try:
            filters = json.loads(row["filters_json"] or "{}")
        except Exception:
            filters = {}
        q = _subscription_filters_to_query(filters if isinstance(filters, dict) else {})
        where, params = _build_filter_sql(q)
        frag, p2 = _cars_dedup_from_fragment(where, params)
        id_tail = " AND cars.id > ?" if " WHERE (" in frag else " WHERE cars.id > ?"
        cat_db = _resolve_catalog_db_path(korea_db, china_db, q)
        conn_cars = _db_connect(cat_db)
        try:
            rows = conn_cars.execute(
                f"""
                SELECT cars.id, cars.car_id, cars.data_json
                FROM cars
                {frag}{id_tail}
                ORDER BY cars.id ASC
                LIMIT 5
                """,
                [*p2, int(row["last_notified_car_pk"] or 0)],
            ).fetchall()
        finally:
            conn_cars.close()
        if not rows:
            continue
        max_pk = max(int(r["id"]) for r in rows)
        lines = [f"Новые авто по подписке: {row['name']}"]
        for r in rows:
            car = json.loads(r["data_json"])
            d = car.get("data") if isinstance(car.get("data"), dict) else {}
            cid = str(r["car_id"])
            title = _car_title(d) or f"Авто {cid}"
            price = d.get("my_price")
            price_text = f"{round(float(price)):,} ₽".replace(",", " ") if price not in (None, "") else "Цена по запросу"
            link = f"{site_url.rstrip('/')}/detail/{cid}" if site_url else f"id={cid}"
            lines.append(f"• {title} — {price_text}\n{link}")
        ok = await _send_tg_message(bot_token, str(row["tg_id"]), "\n".join(lines))
        conn.execute("UPDATE user_subscriptions SET last_notified_car_pk = ?, updated_at = ? WHERE id = ?", [max_pk, _now_iso(), row["id"]])
        conn.commit()
        if ok:
            sent += 1
    return web.json_response({"ok": True, "checked": checked, "sent": sent})


def _request_id_header(request: web.Request) -> str:
    raw = (request.headers.get("X-Request-Id") or "").strip()
    if raw and re.fullmatch(r"[a-zA-Z0-9-]{8,64}", raw):
        return raw
    return secrets.token_hex(8)


def _client_ip_for_rate_limit(request: web.Request) -> str:
    fwd = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if fwd:
        return fwd
    return request.remote or "unknown"


def _env_int(name: str, default: int = 0) -> int:
    try:
        return max(0, int((os.environ.get(name) or "").strip() or str(default)))
    except (TypeError, ValueError):
        return default


def _rate_limit_take(key: str, limit: int) -> bool:
    """True if allowed, False if over limit."""
    if limit <= 0:
        return True
    now = time.monotonic()
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS[key]
        bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW_SEC]
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def create_app(db_path: str, china_db_path: Optional[str] = None) -> web.Application:
    @web.middleware
    async def access_log_middleware(request, handler):
        rid = _request_id_header(request)
        t0 = time.monotonic()
        try:
            resp = await handler(request)
        except Exception:
            dt_ms = int((time.monotonic() - t0) * 1000)
            _LOG.info("%s %s -> error %dms rid=%s", request.method, request.path_qs, dt_ms, rid)
            raise
        dt_ms = int((time.monotonic() - t0) * 1000)
        resp.headers["X-Request-Id"] = rid
        _LOG.info("%s %s -> %s %dms rid=%s", request.method, request.path_qs, resp.status, dt_ms, rid)
        return resp

    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            resp = web.Response(status=204)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, PATCH, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            return resp
        resp = await handler(request)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, PATCH, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resp

    @web.middleware
    async def rate_limit_middleware(request, handler):
        ip = _client_ip_for_rate_limit(request)
        path = request.path
        if request.method == "GET" and path == "/api/cars":
            cars_get_lim = _env_int("WRA_RATE_LIMIT_GET_CARS_PER_MINUTE", 0)
            if cars_get_lim > 0 and not _rate_limit_take(f"get_cars:{ip}", cars_get_lim):
                return web.json_response(
                    {"error": "rate_limit"},
                    status=429,
                    headers={"Retry-After": "60", "Cache-Control": "no-store"},
                )
            return await handler(request)
        if request.method == "GET" and path in ("/api/facets", "/api/filters"):
            facets_lim = _env_int("WRA_RATE_LIMIT_GET_FACETS_PER_MINUTE", 0)
            if facets_lim > 0 and not _rate_limit_take(f"get_facets:{ip}", facets_lim):
                return web.json_response(
                    {"error": "rate_limit"},
                    status=429,
                    headers={"Retry-After": "60", "Cache-Control": "no-store"},
                )
            return await handler(request)
        if request.method != "POST":
            return await handler(request)
        auth_limit = _env_int("WRA_RATE_LIMIT_TELEGRAM_AUTH_PER_MINUTE", 0)
        if path == "/api/auth/telegram" and auth_limit > 0:
            if not _rate_limit_take(f"auth_tg:{ip}", auth_limit):
                return web.json_response(
                    {"error": "rate_limit"},
                    status=429,
                    headers={"Retry-After": "60", "Cache-Control": "no-store"},
                )
            return await handler(request)
        post_limit = _env_int("WRA_RATE_LIMIT_POST_PER_MINUTE", 0)
        if post_limit > 0 and not _rate_limit_take(f"post:{ip}", post_limit):
            return web.json_response(
                {"error": "rate_limit"},
                status=429,
                headers={"Retry-After": "60", "Cache-Control": "no-store"},
            )
        return await handler(request)

    @web.middleware
    async def security_headers_middleware(request, handler):
        resp = await handler(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return resp

    @web.middleware
    async def prometheus_metrics_middleware(request, handler):
        global _METRIC_304_COUNT
        t0 = time.perf_counter()
        resp = await handler(request)
        if (os.environ.get("WRA_PROMETHEUS_METRICS") or "").strip() == "1":
            dt_ms = (time.perf_counter() - t0) * 1000.0
            grp = _metrics_path_group(request.path)
            st = str(resp.status)
            with _METRICS_LOCK:
                _METRIC_REQUESTS[(request.method, grp, st)] += 1
                if resp.status == 304:
                    _METRIC_304_COUNT += 1
                if grp in ("cars", "facets", "car"):
                    _METRIC_DURATION_MS_SUM[grp] += dt_ms
                    _METRIC_DURATION_MS_COUNT[grp] += 1
                    _METRIC_DURATION_SAMPLES[grp].append(dt_ms)
        return resp

    app = web.Application(
        middlewares=[
            access_log_middleware,
            cors_middleware,
            rate_limit_middleware,
            security_headers_middleware,
            prometheus_metrics_middleware,
        ]
    )
    resolved = str(Path(db_path).resolve())
    app[APP_DB_PATH] = resolved
    china_resolved = ""
    if china_db_path and str(china_db_path).strip():
        china_resolved = str(Path(china_db_path).expanduser().resolve())
        Path(china_resolved).parent.mkdir(parents=True, exist_ok=True)
        _bootstrap_cars_table_if_missing(china_resolved)
        _ensure_catalog_indexes(china_resolved)
    app[APP_CHINA_DB_PATH] = china_resolved
    # До приёма трафика: иначе первый запрос держит lock на CREATE INDEX, остальные висят до таймаута nginx.
    _ensure_catalog_indexes(resolved)
    conn = _db_connect(resolved)
    _init_app_tables(conn)
    app[APP_DB] = conn
    app[APP_TELEGRAM_BOT_TOKEN] = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    app[APP_SUBSCRIPTIONS_ADMIN_KEY] = os.environ.get("SUBSCRIPTIONS_ADMIN_KEY", "").strip()
    app[APP_PUBLIC_SITE_URL] = os.environ.get("PUBLIC_SITE_URL", "").strip()
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/metrics", prometheus_metrics)
    app.router.add_get("/api/version", api_version)
    app.router.add_get("/api/cars", cars)
    app.router.add_get("/api/facets", facets)
    app.router.add_get("/api/filters", facets)
    app.router.add_get("/api/stats", catalog_stats)
    app.router.add_get("/api/counts", catalog_counts)
    app.router.add_get("/api/sort", catalog_sort_meta)
    app.router.add_get("/api/sitemap/catalog.xml", sitemap_catalog_xml)
    app.router.add_get("/api/sitemap/index.xml", sitemap_index_xml)
    app.router.add_get("/api/html/car/{id}", car_page_html)
    app.router.add_get("/api/car/{id}", car_by_id)
    app.router.add_get("/api/similar", similar)
    app.router.add_post("/api/auth/telegram", auth_telegram)
    app.router.add_get("/api/me", me)
    app.router.add_post("/api/logout", logout)
    app.router.add_get("/api/favorites", favorites_list)
    app.router.add_post("/api/favorites", favorites_add)
    app.router.add_delete("/api/favorites/{car_id}", favorites_remove)
    app.router.add_get("/api/history", history_list)
    app.router.add_post("/api/history", history_add)
    app.router.add_get("/api/subscriptions", subscriptions_list)
    app.router.add_post("/api/subscriptions", subscriptions_add)
    app.router.add_delete("/api/subscriptions/{sid}", subscriptions_remove)
    app.router.add_get("/api/compare", compare)
    app.router.add_get("/api/checkout", checkout_list)
    app.router.add_post("/api/checkout", checkout_create)
    app.router.add_post("/api/subscriptions/run-notifications", run_subscription_notifications)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Prod Encar API server")
    parser.add_argument("--db", default="encar_cars.db", help="SQLite DB path (Encar / Корея)")
    parser.add_argument(
        "--db-china",
        default=None,
        help="SQLite каталог Dongchedi; иначе переменная окружения WRA_CHINA_DB_PATH",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host")
    parser.add_argument("--port", type=int, default=8080, help="Port")
    args = parser.parse_args()

    if not logging.root.handlers:
        logging.basicConfig(
            level=getattr(logging, (os.environ.get("LOG_LEVEL") or "INFO").upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    db_path = str(Path(args.db).resolve())
    china_arg: Optional[str] = None
    if args.db_china is not None and str(args.db_china).strip():
        china_arg = str(Path(args.db_china).expanduser().resolve())
    else:
        env_ch = (os.environ.get("WRA_CHINA_DB_PATH") or "").strip()
        if env_ch:
            china_arg = str(Path(env_ch).expanduser().resolve())
        else:
            discovered = _discover_china_db_if_unconfigured(db_path)
            if discovered:
                china_arg = discovered
                _LOG.info("China catalog DB auto-discovered: %s", discovered)
    app = create_app(db_path, china_db_path=china_arg)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
