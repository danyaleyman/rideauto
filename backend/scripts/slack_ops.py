"""Slack (Bot Web API + incoming webhook) for ops scripts."""

from __future__ import annotations

import json as json_lib
import os

import requests


def slack_incoming_webhook_from_env() -> str:
    return (os.environ.get("PARSER_AUDIT_SLACK_WEBHOOK") or "").strip()


def slack_app_credentials_from_env() -> tuple[str, str]:
    """Bot User OAuth Token (xoxb-...) + channel id (C… / G…) for chat.postMessage."""
    token = (
        os.environ.get("OPS_SLACK_BOT_TOKEN")
        or os.environ.get("PARSER_AUDIT_SLACK_BOT_TOKEN")
        or os.environ.get("SLACK_BOT_TOKEN")
        or ""
    ).strip()
    channel_id = (
        os.environ.get("OPS_SLACK_CHANNEL_ID") or os.environ.get("PARSER_AUDIT_SLACK_CHANNEL_ID") or ""
    ).strip()
    return token, channel_id


def post_slack_chat_post_message(bot_token: str, channel: str, text: str, *, timeout_sec: float = 15.0) -> None:
    tok = (bot_token or "").strip()
    ch = (channel or "").strip()
    if not tok or not ch:
        return
    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {tok}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"channel": ch, "text": text[:39_000]},
            timeout=timeout_sec,
        )
        body = resp.text[:500]
        if resp.status_code >= 300:
            print(f"slack_chat_http_failed status={resp.status_code} body={body}")
            return
        try:
            data = resp.json()
        except json_lib.JSONDecodeError:
            print(f"slack_chat_bad_json body={body}")
            return
        if not data.get("ok"):
            print(f"slack_chat_api_failed error={data.get('error')!r} body={(resp.text or '')[:400]}")
    except Exception as exc:
        print(f"slack_chat_exception err={exc}")


def notify_slack_alert(
    text: str,
    *,
    webhook_url: str = "",
    bot_token: str = "",
    channel_id: str = "",
) -> bool:
    """Deliver text via Slack app (preferred) or incoming webhook. Returns True if something was sent."""
    bt = (bot_token or "").strip()
    cid = (channel_id or "").strip()
    if bt and cid:
        post_slack_chat_post_message(bt, cid, text)
        return True
    wh = (webhook_url or "").strip()
    if wh:
        post_slack_incoming_webhook(wh, text)
        return True
    return False


def post_slack_incoming_webhook(webhook_url: str, text: str, *, timeout_sec: float = 10.0) -> None:
    if not (webhook_url or "").strip():
        return
    try:
        resp = requests.post(
            webhook_url.strip(),
            json={"text": text[:15_000]},
            timeout=timeout_sec,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 300:
            print(f"slack_post_failed status={resp.status_code} body={(resp.text or '')[:200]}")
    except Exception as exc:
        print(f"slack_post_exception err={exc}")
