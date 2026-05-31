from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from fastapi_app.config import Settings, get_settings
from fastapi_app.lead_telegram import send_lead_telegram_sync, telegram_lead_configured
from fastapi_app.rate_limit import public_rate_limit

router = APIRouter(tags=["forms"])
_log = logging.getLogger(__name__)


class OrderLeadPayload(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    contact_method: str = Field(..., min_length=1, max_length=80)
    message: str = Field(..., min_length=10, max_length=8000)
    pd_agree: bool = Field(..., description="Подтверждение согласия на обработку ПДн")

    @field_validator("full_name", "contact_method", "message")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("pd_agree")
    @classmethod
    def pd_agree_required(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Требуется согласие на обработку персональных данных")
        return v


def _send_lead_email_sync(
    *,
    to_addr: str,
    from_addr: str,
    subject: str,
    body: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    use_tls: bool,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body, charset="utf-8")

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=45) as smtp:
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=45) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)


def _lead_body(payload: OrderLeadPayload, *, lead_id: int | None, rip: str, xf: str | None) -> str:
    return (
        f"ФИО: {payload.full_name}\n"
        f"Предпочтительная связь: {payload.contact_method}\n\n"
        f"Согласие на обработку ПДн: Да\n\n"
        f"Сообщение:\n{payload.message}\n\n"
        f"---\nIP: {rip}\nX-Forwarded-For: {xf or '-'}\n"
        + (f"Lead ID: {lead_id}\n" if lead_id else "")
    )


@router.post("/lead", status_code=status.HTTP_202_ACCEPTED)
@public_rate_limit()
async def submit_order_lead(request: Request, payload: OrderLeadPayload) -> dict:
    """Заявка с сайта: PG + email; Telegram — fallback или дубль."""
    settings = get_settings()
    pool = getattr(request.app.state, "pg_pool", None)
    xf = request.headers.get("x-forwarded-for")
    rip = getattr(request.client, "host", None) or ""
    ua = (request.headers.get("user-agent") or "")[:500]

    host = (settings.lead_smtp_host or settings.auth_smtp_host or "").strip()
    user = (settings.lead_smtp_user or settings.auth_smtp_user or "").strip()
    password = (settings.lead_smtp_password or settings.auth_smtp_password or "").strip()
    smtp_ok = bool(host and user and password)
    tg_ok = telegram_lead_configured(settings)

    if not smtp_ok and not tg_ok:
        _log.warning("lead submit rejected: neither SMTP nor Telegram configured")
        raise HTTPException(
            status_code=503,
            detail="Отправка заявок временно недоступна (не настроена почта на сервере).",
        )

    lead_id: int | None = None
    if pool is not None:
        try:
            lead_id = await pool.fetchval(
                """
                INSERT INTO lead_requests (full_name, contact_method, message, pd_agree, ip, ua)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                payload.full_name,
                payload.contact_method,
                payload.message,
                bool(payload.pd_agree),
                rip or None,
                ua or None,
            )
        except Exception:
            _log.exception("lead insert failed (continuing with delivery)")

    body = _lead_body(payload, lead_id=lead_id, rip=rip or "", xf=xf)
    subject = f"Заявка с сайта — {payload.full_name[:80]}"
    email_sent = False
    telegram_sent = False

    if smtp_ok:
        to_addr = (settings.lead_email_to or "").strip() or user
        from_addr = (settings.lead_email_from or settings.auth_email_from or "").strip() or user
        port = int(settings.lead_smtp_port or settings.auth_smtp_port)
        use_tls = bool(settings.lead_smtp_use_tls or settings.auth_smtp_use_tls)
        from_header = formataddr(("World Ride Auto", from_addr)) if "@" in from_addr else from_addr
        try:
            await asyncio.to_thread(
                _send_lead_email_sync,
                to_addr=to_addr,
                from_addr=from_header,
                subject=subject,
                body=body,
                smtp_host=host,
                smtp_port=port,
                smtp_user=user,
                smtp_password=password,
                use_tls=use_tls,
            )
            email_sent = True
        except OSError:
            _log.exception("lead smtp failed")

    if tg_ok and (not email_sent or settings.lead_telegram_always):
        tg_text = f"🚗 Заявка RideAuto\n\n{body}"
        try:
            await asyncio.to_thread(send_lead_telegram_sync, text=tg_text, settings=settings)
            telegram_sent = True
        except Exception:
            _log.exception("lead telegram failed")

    if not email_sent and not telegram_sent:
        raise HTTPException(
            status_code=502,
            detail="Не удалось отправить заявку. Попробуйте позже или напишите в Telegram.",
        )

    if pool is not None and lead_id is not None and email_sent:
        try:
            await pool.execute(
                "UPDATE lead_requests SET email_sent = true WHERE id = $1",
                int(lead_id),
            )
        except Exception:
            _log.exception("lead email_sent update failed id=%s", lead_id)

    return {"ok": True, "email_sent": email_sent, "telegram_sent": telegram_sent}
