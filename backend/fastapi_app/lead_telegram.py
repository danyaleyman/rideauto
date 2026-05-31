"""Telegram Bot API для заявок с сайта (fallback / дубль email)."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from fastapi_app.config import Settings


def telegram_lead_configured(settings: Settings) -> bool:
    return bool((settings.lead_telegram_bot_token or "").strip() and (settings.lead_telegram_chat_id or "").strip())


def send_lead_telegram_sync(*, text: str, settings: Settings) -> None:
    token = (settings.lead_telegram_bot_token or "").strip()
    chat_id = (settings.lead_telegram_chat_id or "").strip()
    if not token or not chat_id:
        raise RuntimeError("telegram_not_configured")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text[:4000],
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            if not data.get("ok"):
                raise RuntimeError(f"telegram_api_error: {data}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"telegram_http_{exc.code}: {body}") from exc
