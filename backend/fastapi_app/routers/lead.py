from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from fastapi_app.config import get_settings

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


@router.post("/lead", status_code=status.HTTP_202_ACCEPTED)
async def submit_order_lead(request: Request, payload: OrderLeadPayload) -> dict:
    """Заявка с сайта: на почту через SMTP (Yandex и др.), пока без Telegram."""
    settings = get_settings()
    # Primary SMTP from lead settings; fallback to auth SMTP so all forms can use one mailbox.
    host = (settings.lead_smtp_host or settings.auth_smtp_host or "").strip()
    user = (settings.lead_smtp_user or settings.auth_smtp_user or "").strip()
    password = (settings.lead_smtp_password or settings.auth_smtp_password or "").strip()
    if not host or not user or not password:
        _log.warning("lead submit rejected: SMTP not configured")
        raise HTTPException(
            status_code=503,
            detail="Отправка заявок временно недоступна (не настроена почта на сервере).",
        )

    to_addr = (settings.lead_email_to or "").strip() or (settings.auth_smtp_user or "").strip() or "danyaleyman@yandex.ru"
    from_addr = (settings.lead_email_from or settings.auth_email_from or "").strip() or user
    port = int(settings.lead_smtp_port or settings.auth_smtp_port)
    use_tls = bool(settings.lead_smtp_use_tls or settings.auth_smtp_use_tls)

    subject = f"Заявка с сайта — {payload.full_name[:80]}"
    xf = request.headers.get("x-forwarded-for")
    rip = getattr(request.client, "host", None) or ""
    body = (
        f"ФИО: {payload.full_name}\n"
        f"Предпочтительная связь: {payload.contact_method}\n\n"
        f"Согласие на обработку ПДн: Да\n\n"
        f"Сообщение:\n{payload.message}\n\n"
        f"---\nIP: {rip}\nX-Forwarded-For: {xf or '-'}\n"
    )

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
    except OSError as e:
        _log.exception("lead smtp failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail="Не удалось отправить письмо. Попробуйте позже или напишите в Telegram.",
        ) from e

    return {"ok": True}
