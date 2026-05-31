"""Email-уведомления по сохранённым поискам (вызывается из subscriptions router)."""
from __future__ import annotations

import asyncio
import json
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Dict, List, Optional

import asyncpg
from meilisearch import Client

from fastapi_app.config import Settings
from fastapi_app.meilisearch_query import build_meilisearch_filter, meilisearch_sort_list
from fastapi_app.tracing_ops import run_in_thread_traced


def _iso_z(dt: datetime) -> str:
    d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return d.isoformat().replace("+00:00", "Z")


def _filters_to_flat(filters: Any) -> Dict[str, str]:
    if isinstance(filters, dict):
        out: Dict[str, str] = {}
        for k, v in filters.items():
            if v is None:
                continue
            if isinstance(v, list):
                out[str(k)] = ",".join(str(x) for x in v if x is not None and str(x) != "")
            else:
                out[str(k)] = str(v)
        return out
    if isinstance(filters, str):
        try:
            parsed = json.loads(filters)
            return _filters_to_flat(parsed)
        except json.JSONDecodeError:
            return {}
    return {}


def _send_digest_email_sync(
    *,
    to_addr: str,
    subject: str,
    body: str,
    settings: Settings,
) -> None:
    host = (settings.auth_smtp_host or "").strip()
    user = (settings.auth_smtp_user or "").strip()
    password = (settings.auth_smtp_password or "").strip()
    if not host or not user or not password:
        raise RuntimeError("smtp_not_configured")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("World Ride Auto", (settings.auth_email_from or user).strip()))
    msg["To"] = to_addr
    msg.set_content(body, charset="utf-8")
    port = int(settings.auth_smtp_port)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=45) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=45) as smtp:
            if settings.auth_smtp_use_tls:
                smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)


async def _search_new_hits(
    meili: Client,
    settings: Settings,
    flat: Dict[str, str],
    since: Optional[datetime],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    idx = meili.index(settings.meilisearch_index)
    filt = build_meilisearch_filter(flat)
    if since:
        ts = _iso_z(since)
        extra = f'catalog_created_at > "{ts}"'
        filt = f"({filt}) AND ({extra})" if filt else extra
    opts: Dict[str, Any] = {
        "limit": limit,
        "offset": 0,
        "sort": meilisearch_sort_list("date_new"),
    }
    if filt:
        opts["filter"] = filt
    qtext = (flat.get("q") or flat.get("query") or "").strip()

    def _run():
        return idx.search(qtext, opts)

    ms = await run_in_thread_traced("meilisearch.subscription_search", _run)
    return list(ms.get("hits") or [])


async def run_all_subscription_notifications(
    pool: asyncpg.Pool,
    meili: Client,
    settings: Settings,
) -> Dict[str, Any]:
    rows = await pool.fetch(
        """
        SELECT s.id, s.public_id, s.name, s.filters, s.query_string, s.market,
               s.last_notified_at, s.user_id, u.email
        FROM search_subscriptions s
        JOIN auth_users u ON u.id = s.user_id
        WHERE s.notify_enabled = true AND u.is_active = true
        ORDER BY s.id
        """
    )
    processed = 0
    emails_sent = 0
    pushes_sent = 0
    hits_total = 0
    errors: List[str] = []

    from fastapi_app.push_notify import send_push_to_user

    for row in rows:
        processed += 1
        sub_id = int(row["id"])
        user_id = int(row["user_id"])
        email = str(row["email"])
        flat = _filters_to_flat(row["filters"])
        if row["market"] == "china":
            flat.setdefault("region", "china")
            flat.setdefault("source", "che168")
        else:
            flat.setdefault("region", "korea")
            flat.setdefault("source", "encar")
        since = row["last_notified_at"]
        try:
            hits = await _search_new_hits(meili, settings, flat, since)
        except Exception as exc:
            errors.append(f"sub={sub_id}: search failed: {exc}")
            continue
        if not hits:
            await pool.execute(
                "UPDATE search_subscriptions SET updated_at = now() WHERE id = $1",
                sub_id,
            )
            continue
        hits_total += len(hits)
        site = settings.auth_magic_link_base_url.rstrip("/")
        lines = [
            f"Новые объявления по поиску «{row['name'] or 'Каталог'}»:",
            "",
        ]
        for h in hits[:15]:
            cid = str(h.get("id") or h.get("car_id") or "")
            mark = h.get("brand") or h.get("mark") or ""
            model = h.get("model_group") or h.get("model") or ""
            price = h.get("price")
            lines.append(f"• {mark} {model} — {price or 'цена уточняется'} ₽")
            lines.append(f"  {site}/car/{cid}")
            lines.append("")
        qs = (row["query_string"] or "").strip()
        catalog_link = f"{site}/catalog" + (f"?{qs}" if qs else "")
        lines.append(f"Все результаты: {catalog_link}")
        lines.append("")
        lines.append("Отключить уведомления можно в каталоге после входа в аккаунт.")
        body = "\n".join(lines)
        push_title = f"RideAuto: новые авто — {row['name'] or 'поиск'}"
        push_body = f"{len(hits)} новых объявлений. Откройте каталог."
        notified = False
        try:
            await asyncio.to_thread(
                _send_digest_email_sync,
                to_addr=email,
                subject=push_title,
                body=body,
                settings=settings,
            )
            emails_sent += 1
            notified = True
        except Exception as exc:
            errors.append(f"sub={sub_id}: email failed: {exc}")
        try:
            n = await send_push_to_user(
                pool,
                settings,
                user_id,
                title=push_title,
                body=push_body,
                url=catalog_link,
            )
            if n:
                pushes_sent += n
                notified = True
        except Exception as exc:
            errors.append(f"sub={sub_id}: push failed: {exc}")
        if not notified:
            continue
        await pool.execute(
            """
            UPDATE search_subscriptions
            SET last_notified_at = now(), updated_at = now()
            WHERE id = $1
            """,
            sub_id,
        )

    return {
        "ok": True,
        "processed": processed,
        "emails_sent": emails_sent,
        "pushes_sent": pushes_sent,
        "hits_total": hits_total,
        "errors": errors[:20],
    }
