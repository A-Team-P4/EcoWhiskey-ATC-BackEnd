"""Utility helpers for sending transactional emails."""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from app.config.settings import settings


class EmailServiceError(RuntimeError):
    """Raised when the email service cannot deliver a message."""


async def send_email(
    *,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """Send a plain text email with the configured SMTP provider."""

    mail_settings = settings.mail
    if not mail_settings.is_configured():
        raise EmailServiceError("SMTP settings are not configured.")

    message = EmailMessage()
    message["From"] = mail_settings.sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    password = (
        mail_settings.password.get_secret_value()
        if mail_settings.password is not None
        else None
    )

    def _send_sync() -> None:
        context = ssl.create_default_context()
        if mail_settings.use_ssl:
            with smtplib.SMTP_SSL(
                mail_settings.host,
                mail_settings.port,
                context=context,
            ) as client:
                if mail_settings.username and password:
                    client.login(mail_settings.username, password)
                client.send_message(message)
            return

        with smtplib.SMTP(mail_settings.host, mail_settings.port) as client:
            if mail_settings.use_tls:
                client.starttls(context=context)
            if mail_settings.username and password:
                client.login(mail_settings.username, password)
            client.send_message(message)

    try:
        await asyncio.to_thread(_send_sync)
    except (smtplib.SMTPException, OSError) as exc:  # pragma: no cover - network errors
        raise EmailServiceError("Failed to send email.") from exc


__all__ = ["EmailServiceError", "send_email"]
