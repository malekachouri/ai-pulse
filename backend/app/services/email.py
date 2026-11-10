"""Outbound email: SMTP when SMTP_HOST is set, otherwise a console backend that logs a redacted notice.

The console backend never logs the message body (it holds password-reset tokens). Without SMTP, password
reset emails are not delivered - the API logs a warning at startup in production.
"""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import TYPE_CHECKING, Literal, Protocol

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Settings

log = get_logger(__name__)


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        log.info("email_not_sent_console_backend", to=to, subject=subject)


class EmailDeliveryError(Exception):
    pass


class SmtpEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        *,
        username: str | None = None,
        password: str | None = None,
        security: Literal["starttls", "ssl", "none"] = "starttls",
        timeout: float = 20.0,
    ) -> None:
        self.host, self.port, self.sender = host, port, sender
        self.username, self._password = username, password
        self.security, self.timeout = security, timeout

    def _send_sync(self, msg: EmailMessage) -> None:
        context = ssl.create_default_context()
        smtp: smtplib.SMTP
        if self.security == "ssl":
            smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
        else:
            smtp = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        with smtp:
            if self.security == "starttls":
                smtp.starttls(context=context)
            if self.username:
                smtp.login(self.username, self._password or "")
            smtp.send_message(msg)

    async def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        msg["Date"] = formatdate(localtime=False)
        msg["Message-ID"] = make_msgid(domain=self.sender.rsplit("@", 1)[-1].strip("> "))
        msg.set_content(body)
        try:
            await asyncio.to_thread(self._send_sync, msg)
        except (OSError, smtplib.SMTPException) as exc:
            log.error("email_delivery_failed", to=to, subject=subject, error=type(exc).__name__)
            raise EmailDeliveryError("The email could not be sent") from exc
        log.info("email_sent", to=to, subject=subject)


def build_email_sender(settings: Settings) -> EmailSender:
    if not settings.smtp_host:
        if settings.environment == "production":
            log.warning("email_not_configured", detail="SMTP_HOST unset: password reset emails are not sent")
        return ConsoleEmailSender()
    password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
    return SmtpEmailSender(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_from or f"AI Pulse <no-reply@{settings.smtp_host}>",
        username=settings.smtp_username,
        password=password,
        security=settings.smtp_security,
    )


class DeferredEmailSender:
    """Collects messages during a request; `flush` sends them after the response (FastAPI background task).

    Used where the response must not depend on delivery: timing or an SMTP error would otherwise reveal
    whether an account exists (password reset).
    """

    def __init__(self, inner: EmailSender) -> None:
        self.inner = inner
        self.outbox: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.outbox.append((to, subject, body))

    async def flush(self) -> None:
        for to, subject, body in self.outbox:
            try:
                await self.inner.send(to, subject, body)
            except Exception:  # noqa: BLE001 - logged by the sender; never surfaces to the requester
                log.warning("deferred_email_failed", subject=subject)
        self.outbox.clear()
