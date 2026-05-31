"""Web Push (VAPID) для B2C-уведомлений."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

from fastapi_app.config import Settings

_log = logging.getLogger(__name__)


def push_configured(settings: Settings) -> bool:
    return bool(
        (settings.push_vapid_private_key or "").strip()
        and (settings.push_vapid_public_key or "").strip()
    )


def send_web_push_sync(
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    payload: Dict[str, Any],
    settings: Settings,
) -> None:
    from pywebpush import WebPushException, webpush

    vapid = {
        "private_key": (settings.push_vapid_private_key or "").strip(),
        "public_key": (settings.push_vapid_public_key or "").strip(),
        "claims": {"sub": (settings.push_vapid_subject or "mailto:info@rideauto.ru").strip()},
    }
    webpush(
        subscription_info={
            "endpoint": endpoint,
            "keys": {"p256dh": p256dh, "auth": auth},
        },
        data=json.dumps(payload, ensure_ascii=False),
        vapid_private_key=vapid["private_key"],
        vapid_claims=vapid["claims"],
    )


async def send_push_to_user(
    pool: asyncpg.Pool,
    settings: Settings,
    user_id: int,
    *,
    title: str,
    body: str,
    url: str,
) -> int:
    if not push_configured(settings):
        return 0
    rows = await pool.fetch(
        """
        SELECT endpoint, p256dh, auth
        FROM push_subscriptions
        WHERE user_id = $1
        """,
        int(user_id),
    )
    if not rows:
        return 0
    payload = {"title": title[:120], "body": body[:500], "url": url[:2000]}
    sent = 0
    import asyncio

    for row in rows:
        try:
            await asyncio.to_thread(
                send_web_push_sync,
                endpoint=str(row["endpoint"]),
                p256dh=str(row["p256dh"]),
                auth=str(row["auth"]),
                payload=payload,
                settings=settings,
            )
            sent += 1
        except Exception as exc:
            _log.warning("push failed user=%s: %s", user_id, exc)
    return sent
