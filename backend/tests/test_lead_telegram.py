"""Telegram lead delivery helper."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi_app.config import Settings
from fastapi_app.lead_telegram import send_lead_telegram_sync, telegram_lead_configured


def test_telegram_lead_configured():
    s = Settings(lead_telegram_bot_token="tok", lead_telegram_chat_id="123")
    assert telegram_lead_configured(s) is True
    assert telegram_lead_configured(Settings()) is False


def test_send_lead_telegram_ok():
    settings = Settings(lead_telegram_bot_token="tok", lead_telegram_chat_id="123")
    with patch("fastapi_app.lead_telegram.urllib.request.urlopen") as m:
        resp = MagicMock()
        resp.read.return_value = b'{"ok": true}'
        m.return_value.__enter__.return_value = resp
        send_lead_telegram_sync(text="hello", settings=settings)
