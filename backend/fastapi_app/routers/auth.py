from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
import smtplib
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Deque, Dict, Optional

import asyncpg
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from fastapi_app.config import Settings, get_settings
from fastapi_app.schemas.api import (
    AuthMagicRequestPayload,
    AuthMagicVerifyPayload,
    AuthMeResponse,
    AuthSimpleOkResponse,
    AuthUserResponse,
)

router = APIRouter(tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RATE_LOCK = asyncio.Lock()
_RATE_IP_HITS: Dict[str, Deque[float]] = defaultdict(deque)
_RATE_EMAIL_HITS: Dict[str, Deque[float]] = defaultdict(deque)


class FavoritesImportPayload(BaseModel):
    car_ids: list[str] = Field(default_factory=list, max_length=500)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


def _must_auth_enabled(settings: Settings) -> None:
    if not settings.auth_enabled:
        raise HTTPException(status_code=503, detail="auth_disabled")
    if not (settings.auth_secret or "").strip():
        raise HTTPException(status_code=503, detail="auth_secret_not_configured")


def _hash_secret_value(secret: str, value: str) -> str:
    return hashlib.sha256(f"{secret}:{value}".encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return getattr(request.client, "host", "") or ""


async def _check_rate_limit(ip: str, email: str, settings: Settings) -> None:
    now = _now_utc().timestamp()
    cutoff = now - 3600
    async with _RATE_LOCK:
        ip_q = _RATE_IP_HITS[ip]
        while ip_q and ip_q[0] < cutoff:
            ip_q.popleft()
        if len(ip_q) >= settings.auth_rate_limit_per_ip_hour:
            raise HTTPException(status_code=429, detail="too_many_requests")
        ip_q.append(now)

        em_q = _RATE_EMAIL_HITS[email]
        while em_q and em_q[0] < cutoff:
            em_q.popleft()
        if len(em_q) >= settings.auth_rate_limit_per_email_hour:
            raise HTTPException(status_code=429, detail="too_many_requests")
        em_q.append(now)


def _send_magic_email_sync(
    *,
    to_addr: str,
    magic_link: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_use_tls: bool,
    from_addr: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Вход в World Ride Auto"
    msg["From"] = formataddr(("World Ride Auto", from_addr))
    msg["To"] = to_addr
    msg.set_content(
        (
            "Здравствуйте!\n\n"
            "Нажмите на ссылку, чтобы войти в личный кабинет:\n"
            f"{magic_link}\n\n"
            "Ссылка одноразовая и действует ограниченное время.\n"
            "Если это были не вы, просто проигнорируйте письмо."
        ),
        charset="utf-8",
    )
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=45) as smtp:
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=45) as smtp:
            if smtp_use_tls:
                smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)


async def _require_user(request: Request, settings: Settings) -> AuthUserResponse:
    user = await _get_current_user(request, settings)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


async def _get_current_user(request: Request, settings: Settings) -> Optional[AuthUserResponse]:
    token = (request.cookies.get(settings.auth_cookie_name) or "").strip()
    if not token:
        return None
    session_hash = _hash_secret_value(settings.auth_secret, token)
    pool: asyncpg.Pool = request.app.state.pg_pool
    row = await pool.fetchrow(
        """
        SELECT u.id, u.email, u.is_active, u.last_login_at
        FROM auth_sessions s
        JOIN auth_users u ON u.id = s.user_id
        WHERE s.session_hash = $1
          AND s.revoked_at IS NULL
          AND s.expires_at > now()
          AND u.is_active = true
        LIMIT 1
        """,
        session_hash,
    )
    if not row:
        return None
    await pool.execute(
        "UPDATE auth_sessions SET last_seen_at = now() WHERE session_hash = $1",
        session_hash,
    )
    last_login = row["last_login_at"]
    return AuthUserResponse(
        id=int(row["id"]),
        email=str(row["email"]),
        is_active=bool(row["is_active"]),
        last_login_at=last_login.isoformat() if last_login else None,
    )


@router.post("/auth/magic/request", response_model=AuthSimpleOkResponse)
async def auth_magic_request(request: Request, payload: AuthMagicRequestPayload) -> AuthSimpleOkResponse:
    settings = get_settings()
    _must_auth_enabled(settings)
    email = _normalize_email(payload.email)
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="invalid_email")
    ip = _client_ip(request)
    await _check_rate_limit(ip, email, settings)

    smtp_host = (settings.auth_smtp_host or "").strip()
    smtp_user = (settings.auth_smtp_user or "").strip()
    smtp_password = (settings.auth_smtp_password or "").strip()
    if not smtp_host or not smtp_user or not smtp_password:
        raise HTTPException(status_code=503, detail="auth_smtp_not_configured")

    pool: asyncpg.Pool = request.app.state.pg_pool
    user = await pool.fetchrow(
        """
        INSERT INTO auth_users (email, is_active)
        VALUES ($1, true)
        ON CONFLICT (email_norm)
        DO UPDATE SET email = EXCLUDED.email, is_active = true, updated_at = now()
        RETURNING id
        """,
        email,
    )
    user_id = int(user["id"])
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_secret_value(settings.auth_secret, raw_token)
    await pool.execute(
        """
        INSERT INTO auth_magic_tokens (user_id, token_hash, expires_at, ip, ua)
        VALUES ($1, $2, now() + make_interval(mins => $3::int), $4, $5)
        """,
        user_id,
        token_hash,
        int(settings.auth_magic_ttl_min),
        ip or None,
        (request.headers.get("user-agent") or "")[:500] or None,
    )
    base = settings.auth_magic_link_base_url.rstrip("/")
    magic_link = f"{base}/auth/verify?token={raw_token}"
    await asyncio.to_thread(
        _send_magic_email_sync,
        to_addr=email,
        magic_link=magic_link,
        smtp_host=smtp_host,
        smtp_port=int(settings.auth_smtp_port),
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_use_tls=bool(settings.auth_smtp_use_tls),
        from_addr=(settings.auth_email_from or "").strip() or smtp_user,
    )
    return AuthSimpleOkResponse(ok=True)


@router.post("/auth/magic/verify", response_model=AuthSimpleOkResponse)
async def auth_magic_verify(
    request: Request,
    response: Response,
    payload: AuthMagicVerifyPayload,
) -> AuthSimpleOkResponse:
    settings = get_settings()
    _must_auth_enabled(settings)
    token_hash = _hash_secret_value(settings.auth_secret, payload.token.strip())
    pool: asyncpg.Pool = request.app.state.pg_pool
    row = await pool.fetchrow(
        """
        SELECT t.id AS token_id, u.id AS user_id
        FROM auth_magic_tokens t
        JOIN auth_users u ON u.id = t.user_id
        WHERE t.token_hash = $1
          AND t.used_at IS NULL
          AND t.expires_at > now()
          AND u.is_active = true
        LIMIT 1
        """,
        token_hash,
    )
    if not row:
        raise HTTPException(status_code=400, detail="invalid_or_expired_token")
    token_id = int(row["token_id"])
    user_id = int(row["user_id"])

    updated = await pool.fetchval(
        """
        UPDATE auth_magic_tokens
        SET used_at = now()
        WHERE id = $1 AND used_at IS NULL
        RETURNING id
        """,
        token_id,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="invalid_or_expired_token")

    raw_session = secrets.token_urlsafe(32)
    session_hash = _hash_secret_value(settings.auth_secret, raw_session)
    await pool.execute(
        """
        INSERT INTO auth_sessions (user_id, session_hash, expires_at, ip, ua, last_seen_at)
        VALUES ($1, $2, $3, $4, $5, now())
        """,
        user_id,
        session_hash,
        _now_utc() + timedelta(hours=int(settings.auth_session_ttl_hours)),
        _client_ip(request) or None,
        (request.headers.get("user-agent") or "")[:500] or None,
    )
    await pool.execute(
        "UPDATE auth_users SET last_login_at = now(), updated_at = now() WHERE id = $1",
        user_id,
    )

    max_age = int(settings.auth_session_ttl_hours) * 3600
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=raw_session,
        max_age=max_age,
        httponly=True,
        secure=bool(settings.auth_cookie_secure),
        samesite="lax",
        path="/",
    )
    return AuthSimpleOkResponse(ok=True)


@router.post("/auth/logout", response_model=AuthSimpleOkResponse)
async def auth_logout(request: Request, response: Response) -> AuthSimpleOkResponse:
    settings = get_settings()
    token = (request.cookies.get(settings.auth_cookie_name) or "").strip()
    if token:
        pool: asyncpg.Pool = request.app.state.pg_pool
        await pool.execute(
            "UPDATE auth_sessions SET revoked_at = now() WHERE session_hash = $1 AND revoked_at IS NULL",
            _hash_secret_value(settings.auth_secret, token),
        )
    response.delete_cookie(key=settings.auth_cookie_name, path="/")
    return AuthSimpleOkResponse(ok=True)


@router.get("/me", response_model=AuthMeResponse)
@router.get("/auth/me", response_model=AuthMeResponse)
async def auth_me(request: Request) -> AuthMeResponse:
    settings = get_settings()
    user = await _get_current_user(request, settings)
    if not user:
        return AuthMeResponse(authenticated=False, user=None)
    return AuthMeResponse(authenticated=True, user=user)


@router.get("/favorites")
async def get_favorites(request: Request) -> Dict[str, Any]:
    settings = get_settings()
    user = await _require_user(request, settings)
    pool: asyncpg.Pool = request.app.state.pg_pool
    rows = await pool.fetch(
        """
        SELECT f.car_id, f.created_at, c.mark, c.model, c.price_rub
        FROM user_favorites f
        LEFT JOIN cars c ON c.car_id = f.car_id
        WHERE f.user_id = $1
        ORDER BY f.created_at DESC
        """,
        user.id,
    )
    items = [
        {
            "id": str(r["car_id"]),
            "title": " ".join([x for x in [r["mark"], r["model"]] if x]).strip() or str(r["car_id"]),
            "price": r["price_rub"],
            "addedAt": int(r["created_at"].timestamp() * 1000) if r["created_at"] else 0,
        }
        for r in rows
    ]
    return {"result": items}


@router.post("/favorites/{car_id}", response_model=AuthSimpleOkResponse)
async def add_favorite(request: Request, car_id: str) -> AuthSimpleOkResponse:
    settings = get_settings()
    user = await _require_user(request, settings)
    pool: asyncpg.Pool = request.app.state.pg_pool
    await pool.execute(
        """
        INSERT INTO user_favorites (user_id, car_id)
        VALUES ($1, $2)
        ON CONFLICT (user_id, car_id) DO NOTHING
        """,
        user.id,
        car_id.strip(),
    )
    return AuthSimpleOkResponse(ok=True)


@router.delete("/favorites/{car_id}", response_model=AuthSimpleOkResponse)
async def remove_favorite(request: Request, car_id: str) -> AuthSimpleOkResponse:
    settings = get_settings()
    user = await _require_user(request, settings)
    pool: asyncpg.Pool = request.app.state.pg_pool
    await pool.execute(
        "DELETE FROM user_favorites WHERE user_id = $1 AND car_id = $2",
        user.id,
        car_id.strip(),
    )
    return AuthSimpleOkResponse(ok=True)


@router.post("/favorites/import", response_model=AuthSimpleOkResponse)
async def import_favorites(request: Request, payload: FavoritesImportPayload) -> AuthSimpleOkResponse:
    settings = get_settings()
    user = await _require_user(request, settings)
    ids = list(dict.fromkeys([x.strip() for x in payload.car_ids if x and x.strip()]))[:500]
    if not ids:
        return AuthSimpleOkResponse(ok=True)
    pool: asyncpg.Pool = request.app.state.pg_pool
    await pool.executemany(
        """
        INSERT INTO user_favorites (user_id, car_id)
        VALUES ($1, $2)
        ON CONFLICT (user_id, car_id) DO NOTHING
        """,
        [(user.id, cid) for cid in ids],
    )
    return AuthSimpleOkResponse(ok=True)
