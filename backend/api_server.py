#!/usr/bin/env python3
"""
Lightweight API for large catalogs (100k+).

Run:
  python backend/api_server.py --db encar_cars.db --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aiohttp import ClientSession, web


def _db_connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


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
    conn: sqlite3.Connection = request.app["db"]
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
    price_expr = "CAST(json_extract(data_json, '$.data.price_won') AS REAL)"
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
    _add_range_filter(clauses, params, insurance_payout_expr, query.get("ins_payout_from"), query.get("ins_payout_to"))
    _add_range_filter(clauses, params, damaged_expr, query.get("damaged_from"), query.get("damaged_to"))

    if query.get("drive_awd") == "1":
        clauses.append(f"{drive_expr} = 'AWD'")
    if query.get("no_insurance_cases") == "1":
        clauses.append(f"{insurance_cases_expr} = 0")
    if query.get("no_insurance_payouts") == "1":
        clauses.append(f"{insurance_payout_expr} = 0")
    if query.get("no_damaged") == "1":
        clauses.append(f"{damaged_expr} = 0")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def _catalog_query_dict(raw: Dict[str, str]) -> Dict[str, str]:
    skip = frozenset({"page", "per_page", "sort"})
    return {k: v for k, v in raw.items() if k not in skip and v not in (None, "")}


def _facet_dimension(
    conn: sqlite3.Connection,
    query: Dict[str, str],
    omit_keys: frozenset[str],
    value_expr: str,
) -> List[Dict[str, Any]]:
    q2 = {k: v for k, v in query.items() if k not in omit_keys}
    where, params = _build_filter_sql(q2)
    sql = f"""
        SELECT {value_expr} AS val, COUNT(*) AS c
        FROM cars
        {where}
        GROUP BY 1
        HAVING val IS NOT NULL AND CAST(val AS TEXT) <> ''
        ORDER BY val COLLATE NOCASE
    """
    rows = conn.execute(sql, params).fetchall()
    return [{"value": r["val"], "count": r["c"]} for r in rows]


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
    rows = conn.execute(
        """
        SELECT car_id, data_json
        FROM cars
        WHERE json_extract(data_json, '$.data.mark') = ?
          AND CAST(json_extract(data_json, '$.data.price_won') AS REAL) BETWEEN ? AND ?
        ORDER BY ABS(CAST(json_extract(data_json, '$.data.price_won') AS REAL) - ?) ASC, id DESC
        LIMIT ?
        """,
        [mark, pmin, pmax, p, max(limit * 5, limit + 10)],
    ).fetchall()
    return rows


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def cars(request: web.Request) -> web.Response:
    app = request.app
    conn: sqlite3.Connection = app["db"]
    q = request.rel_url.query
    page = max(1, int(q.get("page", "1")))
    per_page = min(100, max(1, int(q.get("per_page", "12"))))
    offset = (page - 1) * per_page

    where, params = _build_filter_sql(q)
    sort = (q.get("sort") or "date_new").strip()
    sort_map = {
        "date_new": "COALESCE(json_extract(data_json, '$.data.offer_created'), json_extract(data_json, '$.data.created_at')) DESC",
        "date_old": "COALESCE(json_extract(data_json, '$.data.offer_created'), json_extract(data_json, '$.data.created_at')) ASC",
        "year_new": "CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER) DESC",
        "year_old": "CAST(SUBSTR(COALESCE(json_extract(data_json, '$.data.year'), ''), 1, 4) AS INTEGER) ASC",
        "price_high": "CAST(json_extract(data_json, '$.data.price_won') AS REAL) DESC",
        "price_low": "CAST(json_extract(data_json, '$.data.price_won') AS REAL) ASC",
        "mileage_high": "CAST(json_extract(data_json, '$.data.km_age') AS INTEGER) DESC",
        "mileage_low": "CAST(json_extract(data_json, '$.data.km_age') AS INTEGER) ASC",
    }
    order_sql = sort_map.get(sort, sort_map["date_new"])
    total = conn.execute(f"SELECT COUNT(*) as c FROM cars {where}", params).fetchone()["c"]
    rows = conn.execute(
        f"SELECT car_id, data_json FROM cars {where} ORDER BY {order_sql}, id DESC LIMIT ? OFFSET ?",
        [*params, per_page, offset],
    ).fetchall()

    result = []
    for row in rows:
        car = json.loads(row["data_json"])
        car["id"] = row["car_id"]
        data = car.get("data") if isinstance(car.get("data"), dict) else car
        if isinstance(data, dict):
            car["title"] = _car_title(data)
            car["price"] = _extract_num(data, "my_price")
            car["year_num"] = int(str(data.get("year") or 0)[:4] or 0)
        result.append(car)

    pages = max(1, (total + per_page - 1) // per_page)
    return web.json_response(
        {
            "result": result,
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
                "next_page": page + 1 if page < pages else None,
            },
        }
    )


async def facets(request: web.Request) -> web.Response:
    conn: sqlite3.Connection = request.app["db"]
    q = _catalog_query_dict(dict(request.rel_url.query))

    mark_expr = "json_extract(data_json, '$.data.mark')"
    model_expr = "json_extract(data_json, '$.data.model')"
    generation_expr = "COALESCE(json_extract(data_json, '$.data.generation'), json_extract(data_json, '$.data.configuration'))"
    trim_expr = "COALESCE(json_extract(data_json, '$.data.gradeName'), json_extract(data_json, '$.data.configuration'), json_extract(data_json, '$.data.generation'))"
    body_expr = "json_extract(data_json, '$.data.body_type')"
    fuel_expr = "json_extract(data_json, '$.data.engine_type')"
    trans_expr = "json_extract(data_json, '$.data.transmission_type')"
    color_expr = "json_extract(data_json, '$.data.color')"

    return web.json_response(
        {
            "marks": _facet_dimension(conn, q, frozenset({"marks"}), mark_expr),
            "models": _facet_dimension(conn, q, frozenset({"models"}), model_expr),
            "generations": _facet_dimension(conn, q, frozenset({"generations"}), generation_expr),
            "trims": _facet_dimension(conn, q, frozenset({"trims"}), trim_expr),
            "bodies": _facet_dimension(conn, q, frozenset({"body"}), body_expr),
            "fuels": _facet_dimension(conn, q, frozenset({"fuel"}), fuel_expr),
            "transmissions": _facet_dimension(conn, q, frozenset({"trans"}), trans_expr),
            "colors": _facet_dimension(conn, q, frozenset({"color"}), color_expr),
        }
    )


async def catalog_stats(request: web.Request) -> web.Response:
    conn: sqlite3.Connection = request.app["db"]
    today_str = datetime.now(timezone.utc).date().isoformat()
    date_expr = (
        "substr(COALESCE(json_extract(data_json, '$.data.offer_created'), "
        "json_extract(data_json, '$.data.created_at')), 1, 10)"
    )
    row = conn.execute(
        f"SELECT COUNT(*) AS c FROM cars WHERE {date_expr} = ?",
        [today_str],
    ).fetchone()
    n = int(row["c"]) if row else 0
    return web.json_response({"listed_today": n, "date_utc": today_str})


async def car_by_id(request: web.Request) -> web.Response:
    app = request.app
    conn: sqlite3.Connection = app["db"]
    car_id = request.match_info.get("id", "").strip()
    if not car_id:
        return web.json_response({"error": "id is required"}, status=400)

    row = conn.execute(
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
    if not row:
        return web.json_response({"error": "not found"}, status=404)

    car = json.loads(row["data_json"])
    car["id"] = row["car_id"]
    return web.json_response({"result": car})


async def similar(request: web.Request) -> web.Response:
    app = request.app
    conn: sqlite3.Connection = app["db"]
    car_id = (request.rel_url.query.get("car_id") or "").strip()
    limit = min(20, max(1, int(request.rel_url.query.get("limit", "8"))))
    if not car_id:
        return web.json_response({"result": [], "meta": {"limit": limit}})

    row = conn.execute(
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
    if not row:
        return web.json_response({"result": [], "meta": {"limit": limit}})

    current = json.loads(row["data_json"])
    current_id = str(row["car_id"])
    rows = _similar_rows(conn, current, limit)
    result = []
    seen_ids = set()
    seen_keys = set()
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
    return web.json_response({"result": result, "meta": {"limit": limit, "count": len(result)}})


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


async def auth_telegram(request: web.Request) -> web.Response:
    conn: sqlite3.Connection = request.app["db"]
    bot_token = request.app.get("telegram_bot_token") or ""
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
    expires_at = datetime.utcfromtimestamp(int(time.time()) + 60 * 60 * 24 * 30).replace(microsecond=0).isoformat() + "Z"
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
    conn: sqlite3.Connection = request.app["db"]
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
    conn = request.app["db"]
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
    admin_key_env = (request.app.get("subscriptions_admin_key") or "").strip()
    if not admin_key_env:
        return web.json_response({"error": "SUBSCRIPTIONS_ADMIN_KEY is not configured"}, status=503)
    admin_key = request.headers.get("X-Admin-Key", "").strip()
    if not admin_key or admin_key != admin_key_env:
        return web.json_response({"error": "forbidden"}, status=403)
    bot_token = (request.app.get("telegram_bot_token") or "").strip()
    if not bot_token:
        return web.json_response({"error": "TELEGRAM_BOT_TOKEN is not configured"}, status=503)

    conn: sqlite3.Connection = request.app["db"]
    site_url = (request.app.get("public_site_url") or "").rstrip("/")
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
        rows = conn.execute(
            f"""
            SELECT id, car_id, data_json
            FROM cars
            {where} {'AND' if where else 'WHERE'} id > ?
            ORDER BY id ASC
            LIMIT 5
            """,
            [*params, int(row["last_notified_car_pk"] or 0)],
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
            link = f"{site_url}/car.html?id={cid}" if site_url else f"id={cid}"
            lines.append(f"• {title} — {price_text}\n{link}")
        ok = await _send_tg_message(bot_token, str(row["tg_id"]), "\n".join(lines))
        conn.execute("UPDATE user_subscriptions SET last_notified_car_pk = ?, updated_at = ? WHERE id = ?", [max_pk, _now_iso(), row["id"]])
        conn.commit()
        if ok:
            sent += 1
    return web.json_response({"ok": True, "checked": checked, "sent": sent})


def create_app(db_path: str) -> web.Application:
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

    app = web.Application(middlewares=[cors_middleware])
    conn = _db_connect(db_path)
    _init_app_tables(conn)
    app["db"] = conn
    app["telegram_bot_token"] = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    app["subscriptions_admin_key"] = os.environ.get("SUBSCRIPTIONS_ADMIN_KEY", "").strip()
    app["public_site_url"] = os.environ.get("PUBLIC_SITE_URL", "").strip()
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/cars", cars)
    app.router.add_get("/api/facets", facets)
    app.router.add_get("/api/stats", catalog_stats)
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

    db_path = str(Path(args.db).resolve())
    app = create_app(db_path)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
