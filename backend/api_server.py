#!/usr/bin/env python3
"""
Lightweight API for large catalogs (100k+).

Run:
  python backend/api_server.py --db encar_cars.db --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import argparse
import asyncio
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
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Tuple

from aiohttp import ClientSession, web

from encar_image_order import _sort_encar_image_url_list, _sort_h_images_list_entries

APP_DB_PATH = web.AppKey("db_path", str)
APP_DB = web.AppKey("db", sqlite3.Connection)
APP_TELEGRAM_BOT_TOKEN = web.AppKey("telegram_bot_token", str)
APP_SUBSCRIPTIONS_ADMIN_KEY = web.AppKey("subscriptions_admin_key", str)
APP_PUBLIC_SITE_URL = web.AppKey("public_site_url", str)

_LOG = logging.getLogger("wra.api")
_RATE_BUCKETS: DefaultDict[str, List[float]] = defaultdict(list)
_RATE_LOCK = threading.Lock()
_RATE_WINDOW_SEC = 60.0

_CATALOG_INDEX_LOCK = threading.Lock()
# Увеличивайте при добавлении индексов — существующие БД получат CREATE INDEX IF NOT EXISTS.
_CATALOG_INDEX_VERSION = 3
_CATALOG_INDEX_STATE: dict[str, int] = {}


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
                )
                conn.commit()
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
    if src == "che168":
        clauses.append("json_extract(data_json, '$.data.source') = ?")
        params.append("che168")
    elif src == "dongchedi":
        clauses.append("json_extract(data_json, '$.data.source') = ?")
        params.append("dongchedi")
    elif src == "encar":
        # Пустой/NULL source в данных считаем Encar; одно выражение проще для планировщика, чем OR из трёх веток.
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
    return (
        "COALESCE("
        "NULLIF(TRIM(json_extract(data_json, '$.data.inner_id')), ''), "
        "NULLIF(TRIM(json_extract(data_json, '$.inner_id')), ''), "
        "NULLIF(TRIM(json_extract(data_json, '$.data.id')), ''), "
        "car_id)"
    )


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
    skip = frozenset({"page", "per_page", "sort", "full"})
    return {k: v for k, v in raw.items() if k not in skip and v not in (None, "")}


def _is_default_first_catalog_page(q: Dict[str, str]) -> bool:
    """Как preload на главной: нет фильтров, page=1, per_page=12, sort=date_new, не full=1."""
    if (q.get("full") or "").strip() == "1":
        return False
    qd = dict(_catalog_query_dict(q))
    src_low = (qd.get("source") or "").strip().lower()
    if src_low == "encar":
        qd.pop("source", None)
    if src_low == "dongchedi":
        qd.pop("source", None)
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


def _cars_catalog_sync(db_path: str, query: Dict[str, str], *, slim: bool) -> Dict[str, Any]:
    _ensure_catalog_indexes(db_path)
    conn = _db_connect(db_path)
    try:
        page = max(1, int(query.get("page", "1") or "1"))
        per_page = min(100, max(1, int(query.get("per_page", "12") or "12")))
        offset = (page - 1) * per_page

        where, params = _build_filter_sql(query)
        from_frag, params2 = _cars_dedup_from_fragment(where, params)
        sort = (query.get("sort") or "date_new").strip()
        order_sql = _CATALOG_SORT_SQL.get(sort, _CATALOG_SORT_SQL["date_new"])
        listing_ids = _catalog_listing_max_ids_subquery(from_frag)
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM cars AS c INNER JOIN {listing_ids} AS x ON c.id = x.mid",
            params2,
        ).fetchone()["c"]
        order_c = _catalog_order_by_alias(order_sql, "c")
        rows = conn.execute(
            f"""
            SELECT c.car_id, c.data_json
            FROM cars AS c
            INNER JOIN {listing_ids} AS x ON c.id = x.mid
            ORDER BY {order_c}
            LIMIT ? OFFSET ?
            """,
            [*params2, per_page, offset],
        ).fetchall()

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
        return {
            "result": result,
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": int(total),
                "pages": pages,
                "next_page": page + 1 if page < pages else None,
                "list_mode": "slim" if slim else "full",
            },
        }
    finally:
        conn.close()


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


def _catalog_stats_sync(db_path: str) -> Dict[str, Any]:
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
        row_total = conn.execute(
            f"SELECT COUNT(*) AS c FROM cars AS c INNER JOIN {listing_ids} AS x ON c.id = x.mid",
            [],
        ).fetchone()
        n_total = int(row_total["c"]) if row_total else 0
        return {"listed_today": n, "date_utc": today_str, "total": n_total}
    finally:
        conn.close()


def _json_public_cache(data: Any, cache_control: str) -> web.Response:
    return web.json_response(data, headers={"Cache-Control": cache_control})


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


async def health(_: web.Request) -> web.Response:
    body: Dict[str, Any] = {"status": "ok"}
    sha = (os.environ.get("WRA_GIT_SHA") or os.environ.get("GIT_COMMIT") or "").strip()
    if sha:
        body["git_sha"] = sha
    return web.json_response(body)


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
    slim = (q.get("full") or "").strip() != "1"
    db_path: str = request.app[APP_DB_PATH]
    payload = await asyncio.to_thread(_cars_catalog_sync, db_path, q, slim=slim)
    # Первая страница без фильтров (как у конкурента с «мгновенным» списком после preload) — дольше SWR у клиента.
    if slim and _is_default_first_catalog_page(q):
        cache = "public, max-age=120, stale-while-revalidate=600"
    elif slim:
        cache = "public, max-age=60, stale-while-revalidate=180"
    else:
        cache = "public, max-age=20, stale-while-revalidate=120"
    return _json_public_cache(payload, cache)


async def facets(request: web.Request) -> web.Response:
    q = _catalog_query_dict({k: str(v) if not isinstance(v, str) else v for k, v in request.rel_url.query.items()})
    db_path: str = request.app[APP_DB_PATH]
    try:
        payload = await asyncio.to_thread(_facets_catalog_sync, db_path, q)
    except Exception as e:
        return web.json_response(
            {"error": "facets_unavailable", "detail": str(e)[:500]},
            status=503,
            headers={"Cache-Control": "no-store"},
        )
    return _json_public_cache(payload, "public, max-age=60, stale-while-revalidate=180")


async def catalog_stats(request: web.Request) -> web.Response:
    db_path: str = request.app[APP_DB_PATH]
    payload = await asyncio.to_thread(_catalog_stats_sync, db_path)
    return _json_public_cache(payload, "public, max-age=60, stale-while-revalidate=300")


async def catalog_counts(request: web.Request) -> web.Response:
    """Как у конкурента: тот же payload, что /api/stats (+ total), отдельный URL для micro-cache."""
    return await catalog_stats(request)


async def catalog_sort_meta(_: web.Request) -> web.Response:
    opts = [{"value": v, "title": t, "hint": h} for v, t, h in _CATALOG_SORT_META]
    return _json_public_cache(
        {"options": opts},
        "public, max-age=3600, stale-while-revalidate=86400",
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


async def car_by_id(request: web.Request) -> web.Response:
    car_id = request.match_info.get("id", "").strip()
    db_path: str = request.app[APP_DB_PATH]
    status, body = await asyncio.to_thread(_car_by_id_sync, db_path, car_id)
    if status == 200:
        return _json_public_cache(body, "public, max-age=45, stale-while-revalidate=300")
    return web.json_response(body, status=status)


async def similar(request: web.Request) -> web.Response:
    car_id = (request.rel_url.query.get("car_id") or "").strip()
    try:
        limit = min(20, max(1, int(request.rel_url.query.get("limit", "8"))))
    except (TypeError, ValueError):
        limit = 8
    db_path: str = request.app[APP_DB_PATH]
    payload = await asyncio.to_thread(_similar_sync, db_path, car_id, limit)
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
    conn = request.app[APP_DB]
    ids = [x.strip() for x in (request.rel_url.query.get("ids") or "").split(",") if x.strip()]
    ids = ids[:4]
    result: List[Dict[str, Any]] = []
    for cid in ids:
        row = _car_row_by_any_id(conn, cid)
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
        rows = conn.execute(
            f"""
            SELECT cars.id, cars.car_id, cars.data_json
            FROM cars
            {frag}{id_tail}
            ORDER BY cars.id ASC
            LIMIT 5
            """,
            [*p2, int(row["last_notified_car_pk"] or 0)],
        ).fetchall()
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


def create_app(db_path: str) -> web.Application:
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
        if request.method != "POST":
            return await handler(request)
        ip = _client_ip_for_rate_limit(request)
        path = request.path
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

    app = web.Application(middlewares=[access_log_middleware, cors_middleware, rate_limit_middleware])
    resolved = str(Path(db_path).resolve())
    app[APP_DB_PATH] = resolved
    # До приёма трафика: иначе первый запрос держит lock на CREATE INDEX, остальные висят до таймаута nginx.
    _ensure_catalog_indexes(resolved)
    conn = _db_connect(resolved)
    _init_app_tables(conn)
    app[APP_DB] = conn
    app[APP_TELEGRAM_BOT_TOKEN] = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    app[APP_SUBSCRIPTIONS_ADMIN_KEY] = os.environ.get("SUBSCRIPTIONS_ADMIN_KEY", "").strip()
    app[APP_PUBLIC_SITE_URL] = os.environ.get("PUBLIC_SITE_URL", "").strip()
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/version", api_version)
    app.router.add_get("/api/cars", cars)
    app.router.add_get("/api/facets", facets)
    app.router.add_get("/api/filters", facets)
    app.router.add_get("/api/stats", catalog_stats)
    app.router.add_get("/api/counts", catalog_counts)
    app.router.add_get("/api/sort", catalog_sort_meta)
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
    parser.add_argument("--db", default="encar_cars.db", help="SQLite DB path")
    parser.add_argument("--host", default="127.0.0.1", help="Host")
    parser.add_argument("--port", type=int, default=8080, help="Port")
    args = parser.parse_args()

    if not logging.root.handlers:
        logging.basicConfig(
            level=getattr(logging, (os.environ.get("LOG_LEVEL") or "INFO").upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    db_path = str(Path(args.db).resolve())
    app = create_app(db_path)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
